# -*- coding: utf-8 -*-
"""Проверка мгновенной синхронизации против БОЕВОГО Supabase.

Realtime — единственная часть графика, которую нельзя проверить на поддельном сервере:
там нет ни репликации, ни публикации, ни Phoenix-канала. Поэтому здесь настоящий
браузер подключается к настоящему проекту тем же кодом, что и приложение
(`rtConnect()` из шаблона), а скрипт тем временем меняет строку в базе и смотрит,
доехало ли событие.

Важная деталь, на которой тест сначала обманулся: канал открывается с любым токеном,
но подписку сервер принимает **только по настоящему JWT** — с выдуманным приходит
`phx_reply`, и на этом всё, событий не будет никогда. Поэтому тест заводит временного
пользователя, входит им по-настоящему и в конце его удаляет.

Боевые данные не страдают: правится только служебный вид события, он же удаляется.

    SUPABASE_TOKEN=sbp_… python scripts/94_realtime_test.py
"""
import os, sys, json, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / 'build' / 'app' / 'index.html'
PROJECT = 'bprfxixyqonjboxyrnyc'
TOKEN = os.environ.get('SUPABASE_TOKEN', '')
if not TOKEN:
    sys.exit('Нужен токен: SUPABASE_TOKEN=sbp_… python scripts/94_realtime_test.py')

AUTH = json.load(open(ROOT / 'data' / 'auth.json', encoding='utf-8'))
if not AUTH.get('url'):
    sys.exit('Вход выключен (пустой url в data/auth.json) — проверять нечего.')

MAIL, PASS = 'rt-test@tokyo.local', 'RtTest!2026'
MARK = 'RT-проверка'
errs = []


def check(name, cond, extra=''):
    print(('  ok  ' if cond else 'FAIL  ') + name + (('  ' + extra) if extra and not cond else ''))
    if not cond:
        errs.append(name)


def mgmt(path, method='GET', body=None):
    req = urllib.request.Request(
        f'https://api.supabase.com/v1/projects/{PROJECT}{path}',
        data=json.dumps(body).encode('utf-8') if body is not None else None,
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json',
                 'User-Agent': 'curl/8.4.0'}, method=method)
    return json.load(urllib.request.urlopen(req))


def sql(q):
    return mgmt('/database/query', 'POST', {'query': q})


def api(path, body=None, key=None, method='POST'):
    k = key or AUTH['key']
    req = urllib.request.Request(
        AUTH['url'] + path,
        data=json.dumps(body).encode('utf-8') if body is not None else None,
        headers={'apikey': k, 'Authorization': 'Bearer ' + k,
                 'Content-Type': 'application/json', 'User-Agent': 'curl/8.4.0'}, method=method)
    try:
        r = urllib.request.urlopen(req)
        txt = r.read().decode()
        return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        return {'ERR': e.code, 'body': e.read().decode()[:300]}


# --- служебный аккаунт: заводим, входим, в конце убираем
service = next((k['api_key'] for k in mgmt('/api-keys?reveal=true')
                if k.get('name') == 'service_role'), None)
if not service:
    sys.exit('Не удалось получить service_role ключ проекта.')

sql(f"delete from public.event_kinds where name like '{MARK}%'")
uid = None
u = api('/auth/v1/admin/users', {'email': MAIL, 'password': PASS, 'email_confirm': True,
                                 'app_metadata': {'role': 'owner', 'dept': 'bar',
                                                  'category': 3, 'venue': 'ТС-45'}}, service)
uid = u.get('id')
if not uid:                                    # уже существует с прошлого прогона
    found = api('/auth/v1/admin/users?per_page=200', None, service, 'GET')
    uid = next((x['id'] for x in found.get('users', []) if x.get('email') == MAIL), None)
tok = api('/auth/v1/token?grant_type=password', {'email': MAIL, 'password': PASS})
jwt = tok.get('access_token')
if not jwt:
    sys.exit(f'Не удалось войти служебным аккаунтом: {tok}')

venue = sql("select id from public.venues where is_own limit 1")[0]['id']

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={'width': 390, 'height': 844})
        js_errors = []
        pg.on('pageerror', lambda e: js_errors.append(str(e)))

        # Сеть настоящая: ничего не перехватываем.
        pg.add_init_script('''(() => {
          const S = %s;
          try{ localStorage.setItem('barquiz.auth', JSON.stringify(S)); }catch(e){}
          window.__rtHits = 0;
        })()''' % json.dumps({'token': jwt, 'refresh': tok.get('refresh_token', ''),
                              'uid': uid, 'mail': MAIL, 'role': 'owner', 'cat': 3,
                              'dept': 'bar', 'venue': 'ТС-45',
                              'exp': 9999999999000}, ensure_ascii=False))
        pg.goto(APP.as_uri())
        pg.wait_for_timeout(800)

        # Считаем сами события канала, а не перерисовки: так проверка не зависит
        # от того, успел ли клиент перечитать данные.
        pg.evaluate('''() => {
          window.__rtHits = 0;
          window.rtTouched = function(){ window.__rtHits++; };
          window.__rtState = () => (RT.ws ? RT.ws.readyState : -1);
          rtConnect();
        }''')

        def wait_for(js, tries=100, gap=200):
            for _ in range(tries):
                pg.wait_for_timeout(gap)
                if pg.evaluate(js):
                    return True
            return False

        # Подключение идёт через интернет и иногда не успевает с первого раза.
        # Одна повторная попытка убирает мигание проверки, не пряча настоящую поломку:
        # если Realtime сломан, не поможет и десять попыток.
        opened = wait_for('window.__rtState() === 1', tries=60)
        if not opened:
            pg.evaluate('RT.ws = null; rtConnect();')
            opened = wait_for('window.__rtState() === 1', tries=60)
        check('канал Realtime открылся', opened,
              f'readyState={pg.evaluate("window.__rtState()")}')
        check('подписка принята сервером', wait_for('RT.joined'))

        def expect_event(name, q):
            before = pg.evaluate('window.__rtHits')
            sql(q)
            check(name, wait_for(f'window.__rtHits > {before}'),
                  f'событий {pg.evaluate("window.__rtHits")}')

        expect_event('вставка доезжает до клиента',
                     f"""insert into public.event_kinds (venue_id, dept, name, color, sort)
                         values ('{venue}', 'bar', '{MARK}', '#E0A45B', 999)""")
        expect_event('правка доезжает',
                     f"update public.event_kinds set hour_bonus = 7 where name = '{MARK}'")
        expect_event('удаление доезжает (replica identity full)',
                     f"delete from public.event_kinds where name = '{MARK}'")

        # Смены — самая частая правка, проверяем и их.
        p = sql("select id, venue_id, d_from::text from public.periods order by d_from desc limit 1")[0]
        st = sql("select id from public.staff limit 1")[0]['id']
        expect_event('смена доезжает',
                     f"""insert into public.shifts (period_id, staff_id, venue_id, day, layer, kind, start_h, end_h)
                         values ('{p['id']}','{st}','{p['venue_id']}','{p['d_from']}','wish','work',9,10)""")
        sql(f"""delete from public.shifts where period_id='{p['id']}' and layer='wish'
                and start_h=9 and end_h=10""")

        # Уход в фон обязан закрывать сокет: держать его открытым в кармане незачем.
        pg.evaluate("Object.defineProperty(document,'hidden',{get:()=>true,configurable:true});"
                    "dispatchEvent(new Event('visibilitychange'))")
        pg.wait_for_timeout(700)
        check('в фоне сокет закрывается', pg.evaluate('window.__rtState()') != 1,
              f'readyState={pg.evaluate("window.__rtState()")}')

        check('нет ошибок в консоли', not js_errors, ' | '.join(js_errors[:3]))
        b.close()
finally:
    sql(f"delete from public.event_kinds where name like '{MARK}%'")
    if uid:
        api(f'/auth/v1/admin/users/{uid}', None, service, 'DELETE')

print(f'\nпровалено: {len(errs)}')
sys.exit(1 if errs else 0)
