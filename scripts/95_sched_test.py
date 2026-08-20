# -*- coding: utf-8 -*-
"""Экран графика на поддельном сервере: чтение, ввод смены, цикл выкатки, сотрудники.

Реальный Supabase не нужен — запросы к `/rest/v1/...` перехватываются Playwright.
Но и статической заглушки мало: половина ценности экрана в том, что смена
сохраняется. Поэтому здесь маленький PostgREST в памяти — он понимает `col=eq.значение`,
POST, PATCH и DELETE. Тест ставит смену через интерфейс и проверяет, что до «сервера»
доехала ровно та строка, которую ждали.

Фикстура `data/sched_fixture.json` — слепок боевых строк (104 смены за вторую половину
августа), чтобы формы данных совпадали с продакшеном.

    python scripts/95_sched_test.py            прогон
    python scripts/95_sched_test.py --shot     + снимки в build/
"""
import sys, json, copy, pathlib, urllib.parse
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / 'build' / 'app' / 'index.html'
BASE = json.load(open(ROOT / 'data' / 'sched_fixture.json', encoding='utf-8'))
SHOT = '--shot' in sys.argv
errs = []
DB = copy.deepcopy(BASE)
LOG = []                       # что уходило на запись — по нему и проверяем
GETS = []                      # чтения: по ним ловим лишние запросы


def check(name, cond, extra=''):
    print(('  ok  ' if cond else 'FAIL  ') + name + (('  ' + extra) if extra and not cond else ''))
    if not cond:
        errs.append(name)


def match(row, params):
    """PostgREST-фильтры вида col=eq.value. Больше нам не нужно."""
    for key, vals in params.items():
        if key in ('select', 'order', 'limit'):
            continue
        want = vals[0]
        if not want.startswith('eq.'):
            continue
        want = want[3:]
        got = row.get(key)
        if str(got) != want:
            return False
    return True


def handle(route, request):
    u = urllib.parse.urlparse(request.url)
    table = u.path.rsplit('/', 1)[-1]
    params = urllib.parse.parse_qs(u.query)
    rows = DB.setdefault(table, [])
    m = request.method

    if m == 'GET':
        GETS.append(table)
        out = [r for r in rows if match(r, params)]
        return route.fulfill(status=200, content_type='application/json',
                             body=json.dumps(out, ensure_ascii=False))
    body = json.loads(request.post_data or 'null')
    LOG.append((m, table, params, body))
    if m == 'POST':
        items = body if isinstance(body, list) else [body]
        for it in items:
            it.setdefault('id', f'{table}-{len(rows)}-{len(LOG)}')
            # Часы считает база генерируемой колонкой — повторяем то же правило,
            # иначе сумма в сетке после сохранения разъедется с боевой.
            if table == 'shifts':
                s, e = it.get('start_h'), it.get('end_h')
                it['hours'] = 0 if (it.get('kind') != 'work' or s is None or e is None) \
                    else (24 if e == s else (e - s + 24) % 24)
            rows.append(it)
        return route.fulfill(status=201, content_type='application/json', body='[]')
    if m == 'PATCH':
        for r in rows:
            if match(r, params):
                r.update(body)
        return route.fulfill(status=204, body='')
    if m == 'DELETE':
        DB[table] = [r for r in rows if not match(r, params)]
        return route.fulfill(status=204, body='')
    route.fulfill(status=200, content_type='application/json', body='[]')


def writes(table, method):
    return [x for x in LOG if x[1] == table and x[0] == method]


with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    js_errors = []
    pg.on('console', lambda m: js_errors.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: js_errors.append(str(e)))

    # Владелец: is_boss() в приложении true и без карточки сотрудника.
    pg.add_init_script('''
      try{ localStorage.setItem('barquiz.auth', JSON.stringify(
        {token:'t', refresh:'r', uid:'test-uid', mail:'test@local',
         role:'owner', cat:3, dept:'bar', venue:'ТС-45', exp:Date.now()+36e5})); }catch(e){}
    ''')
    pg.route('**/rest/v1/**', handle)
    pg.route('**/auth/v1/**', lambda r: r.fulfill(
        status=200, content_type='application/json',
        body='{"access_token":"t","refresh_token":"r","expires_in":3600}'))
    pg.goto(APP.as_uri())
    pg.wait_for_timeout(400)

    # ---------------------------------------------------------------- чтение
    pg.click('[data-mode="sched"]')
    pg.wait_for_timeout(600)
    check('экран графика открылся', pg.locator('#sched').is_visible())
    check('заголовок периода заполнен',
          pg.locator('#schTitle').inner_text().strip() not in ('', '—'))
    rows = pg.locator('.schgrid tbody tr').count()
    check('строк по числу сотрудников', rows == len(BASE['staff']), str(rows))
    cols = pg.locator('.schgrid thead th').count() - 1
    check('колонок по числу дней', cols == 16, str(cols))
    want = sum(s['hours'] or 0 for s in BASE['shifts'] if s['layer'] == 'plan')
    got = pg.evaluate('''() => [...document.querySelectorAll('.schgrid tbody .nm span')]
        .reduce((a,e)=>a+parseInt(e.textContent)||a, 0)''')
    check('часы сходятся с базой', got == want, f'{got} против {want}')
    check('выходные подсвечены', pg.locator('.schgrid td.c.off').count() > 0)
    check('прилипшая колонка имён', pg.evaluate(
        "getComputedStyle(document.querySelector('.schgrid .nm')).position") == 'sticky')

    # ------------------------------------------------------ панель старшего
    check('панель старшего видна', pg.locator('#schEdit').count() == 1)
    check('до включения правки клетки не тапаются', pg.locator('.schgrid td.c.ed').count() == 0)
    pg.click('#schEdit'); pg.wait_for_timeout(200)
    check('правка включилась', pg.locator('.schgrid td.c.ed').count() > 0)
    GETS.clear()

    # ---------------------------------------------------------- ввод смены
    pg.locator('.schgrid td.c.ed').first.click()
    pg.wait_for_timeout(300)
    check('нижний лист открылся', pg.locator('#schModal.on').count() == 1)
    check('есть частые смены', pg.locator('#schCard [data-q]').count() >= 5)
    # У выходного часов нет, поэтому рядов тоже — проверяем после выбора смены.
    check('у выходного рядов часов нет', pg.locator('#schCard .hb').count() == 0)
    pg.click('#schCard [data-q="16-04"]'); pg.wait_for_timeout(150)
    check('есть два ряда часов по 24', pg.locator('#schCard .hb').count() == 48,
          str(pg.locator('#schCard .hb').count()))
    check('выбранный час подсвечен', pg.locator('#hrowA .hb.on').inner_text() == '16')
    pg.click('#schCellSave'); pg.wait_for_timeout(600)
    check('лист закрылся после сохранения', pg.locator('#schModal.on').count() == 0)
    posted = writes('shifts', 'POST')
    check('смена ушла на сервер', len(posted) == 1, str(len(posted)))
    if posted:
        row = posted[-1][3][0]
        check('смена 16-04 с часами и слоем plan',
              row['start_h'] == 16 and row['end_h'] == 4 and row['layer'] == 'plan'
              and row['kind'] == 'work', json.dumps(row, ensure_ascii=False))
    check('клетка перезаписывается целиком (был DELETE)', len(writes('shifts', 'DELETE')) == 1)
    # Правка клетки не должна перечитывать справочник: точки, сотрудники, виды
    # и список периодов от неё не меняются. Раньше на каждое сохранение уходило
    # пять лишних запросов.
    check('сохранение смены не тянет справочник',
          'staff' not in GETS[-6:] and 'venues' not in GETS[-6:] and 'event_kinds' not in GETS[-6:],
          ', '.join(GETS[-6:]))

    # выходной: один тап, вся клетка становится выходным
    pg.locator('.schgrid td.c.ed').nth(3).click(); pg.wait_for_timeout(300)
    pg.click('#schCard [data-off]'); pg.wait_for_timeout(120)
    pg.click('#schCellSave'); pg.wait_for_timeout(600)
    row = writes('shifts', 'POST')[-1][3][0]
    check('выходной без часов', row['kind'] == 'off' and row['start_h'] is None,
          json.dumps(row, ensure_ascii=False))

    # вторая смена за день
    pg.locator('.schgrid td.c.ed').first.click(); pg.wait_for_timeout(300)
    if pg.locator('#schAdd').count():
        pg.click('#schAdd'); pg.wait_for_timeout(120)
        pg.click('#schCard [data-q="10-18"]'); pg.wait_for_timeout(120)
        pg.click('#schCellSave'); pg.wait_for_timeout(600)
        sent = writes('shifts', 'POST')[-1][3]
        check('две смены за день сохраняются вместе', len(sent) == 2,
              json.dumps(sent, ensure_ascii=False))
    else:
        check('две смены за день сохраняются вместе', False, 'кнопки «+ смена» нет')

    if SHOT:
        pg.screenshot(path=str(ROOT / 'build' / 'sched-edit.png'), full_page=True)

    # ------------------------------------------------------ цикл состояний
    # Период фикстуры уже выкачен (историю импорт заливает published), поэтому
    # цикл проверяем полностью: вернуть в черновик -> выкатить заново.
    check('у выкаченного есть возврат в черновик', pg.locator('#schToDraft2').count() == 1)
    pg.click('#schToDraft2'); pg.wait_for_timeout(600)
    check('состояние стало черновиком',
          writes('periods', 'PATCH')[-1][3]['state'] == 'draft')
    check('в черновике доступна выкатка', pg.locator('#schPub').count() == 1)
    pg.click('#schPub'); pg.wait_for_timeout(600)
    patched = writes('periods', 'PATCH')
    check('выкатка меняет состояние', patched and patched[-1][3]['state'] == 'published',
          json.dumps(patched[-1][3] if patched else {}, ensure_ascii=False))
    check('в выкатке есть автор и время',
          bool(patched and patched[-1][3].get('published_by') and patched[-1][3].get('published_at')))

    # ---------------------------------------------------------- сотрудники
    pg.click('#schStaff'); pg.wait_for_timeout(400)
    check('экран сотрудников открылся', pg.locator('#staffscr').is_visible())
    check('карточек по числу сотрудников',
          pg.locator('.strow').count() == len(BASE['staff']), str(pg.locator('.strow').count()))
    pg.locator('.strow').first.locator('[data-senior]').click()
    pg.wait_for_timeout(500)
    st = writes('staff', 'PATCH')
    check('назначение старшего уходит на сервер',
          st and st[-1][3].get('sched_role') == 'senior',
          json.dumps(st[-1][3] if st else {}, ensure_ascii=False))
    pg.locator('.strow').first.locator('[data-cat="3"]').click()
    pg.wait_for_timeout(500)
    st = writes('staff', 'PATCH')
    check('категория уходит на сервер', st and st[-1][3].get('category') == 3,
          json.dumps(st[-1][3] if st else {}, ensure_ascii=False))
    if SHOT:
        pg.screenshot(path=str(ROOT / 'build' / 'sched-staff.png'), full_page=True)

    # ------------------------------------------- события дня и комментарии
    pg.click('[data-sched="1"]'); pg.wait_for_timeout(500)
    ev_day = BASE['day_events'][0]['day']
    pg.click(f'.schgrid thead th[data-day="{ev_day}"]'); pg.wait_for_timeout(400)
    check('лист дня открылся', pg.locator('#schModal.on').count() == 1)
    check('событие дня показано', pg.locator('#schCard .evrow').count() >= 1)
    check('виды событий предложены',
          pg.locator('#schCard [data-evadd]').count() == len(BASE['event_kinds']),
          str(pg.locator('#schCard [data-evadd]').count()))
    free = [k for k in BASE['event_kinds'] if k['name'] != 'Квиз'][0]
    pg.click(f'#schCard [data-evadd="{free["id"]}"]'); pg.wait_for_timeout(600)
    ev = writes('day_events', 'POST')
    check('событие ставится на день', ev and ev[-1][3]['kind_id'] == free['id'],
          json.dumps(ev[-1][3] if ev else {}, ensure_ascii=False))
    pg.fill('#dayNote', 'проверка комментария')
    pg.click('#dayNoteAdd'); pg.wait_for_timeout(600)
    nt = writes('day_notes', 'POST')
    check('комментарий к дню сохраняется',
          nt and nt[-1][3]['body'] == 'проверка комментария',
          json.dumps(nt[-1][3] if nt else {}, ensure_ascii=False))
    # Ручной лимит на конкретный день — уходит в настройки точки, а не в день.
    pg.fill('#ovrH', '150'); pg.fill('#ovrM', '5')
    pg.click('#ovrSave'); pg.wait_for_timeout(600)
    ss = writes('sched_settings', 'PATCH')
    check('ручной лимит дня сохраняется',
          ss and ss[-1][3]['data'].get('day_override', {}).get(ev_day, {}).get('hours') == 150,
          json.dumps(ss[-1][3] if ss else {}, ensure_ascii=False)[:200])
    if SHOT:
        pg.screenshot(path=str(ROOT / 'build' / 'sched-day.png'), full_page=True)
    pg.click('#schCellClose'); pg.wait_for_timeout(300)

    # ------------------------------------------------- границы периода
    pg.click('#schPeriod'); pg.wait_for_timeout(400)
    check('лист границ открылся', pg.locator('#perFrom').count() == 1)
    check('границы взяты из периода',
          pg.input_value('#perFrom') == BASE['periods'][3]['d_from'],
          pg.input_value('#perFrom'))
    pg.click('#schCard [data-len="7"]'); pg.wait_for_timeout(300)
    check('быстрая длина меняет конец',
          pg.input_value('#perTo') != BASE['periods'][3]['d_to'], pg.input_value('#perTo'))
    pg.fill('#perTitle', 'Проба')
    pg.click('#perSave'); pg.wait_for_timeout(700)
    pp = writes('periods', 'PATCH')
    check('границы уходят на сервер',
          pp and pp[-1][3].get('title') == 'Проба' and pp[-1][3].get('d_to'),
          json.dumps(pp[-1][3] if pp else {}, ensure_ascii=False))

    # ------------------------------------------------- настройки и виды
    pg.click('#schSettings'); pg.wait_for_timeout(500)
    check('настройки открылись', pg.locator('#setsscr').is_visible())
    check('семь дней недели в лимитах', pg.locator('#setsBody [data-hl]').count() == 7)
    pg.locator('#setsBody [data-hl="1"]').fill('120')
    pg.locator('#setsBody [data-hl="1"]').dispatch_event('change')
    pg.wait_for_timeout(600)
    ss = writes('sched_settings', 'PATCH')
    check('лимит часов по дню недели сохраняется',
          ss and ss[-1][3]['data'].get('hour_limit', {}).get('1') == 120,
          json.dumps(ss[-1][3]['data'].get('hour_limit') if ss else {}, ensure_ascii=False))
    pg.fill('#quickNew', '14-02')
    pg.click('#quickAdd'); pg.wait_for_timeout(600)
    ss = writes('sched_settings', 'PATCH')
    check('частая смена добавляется', ss and '14-02' in (ss[-1][3]['data'].get('quick') or []),
          json.dumps(ss[-1][3]['data'].get('quick') if ss else [], ensure_ascii=False))
    if SHOT:
        pg.screenshot(path=str(ROOT / 'build' / 'sched-sets.png'), full_page=True)

    pg.click('#setsKinds'); pg.wait_for_timeout(500)
    check('справочник видов открылся', pg.locator('#kindsscr').is_visible())
    check('виды выведены', pg.locator('#kindsBody .strow').count() == len(BASE['event_kinds']))
    pg.locator('#kindsBody .strow').first.locator('[data-kbonus]').fill('12')
    pg.locator('#kindsBody .strow').first.locator('[data-kbonus]').dispatch_event('change')
    pg.wait_for_timeout(600)
    kk = writes('event_kinds', 'PATCH')
    check('надбавка часов у вида сохраняется', kk and kk[-1][3].get('hour_bonus') == 12,
          json.dumps(kk[-1][3] if kk else {}, ensure_ascii=False))
    pg.locator('#kindsBody .strow').first.locator('[data-kcolor]').nth(2).click()
    pg.wait_for_timeout(600)
    kk = writes('event_kinds', 'PATCH')
    check('цвет вида сохраняется', kk and kk[-1][3].get('color'),
          json.dumps(kk[-1][3] if kk else {}, ensure_ascii=False))
    if SHOT:
        pg.screenshot(path=str(ROOT / 'build' / 'sched-kinds.png'), full_page=True)

    check('нет ошибок в консоли', not js_errors, ' | '.join(js_errors[:3]))
    b.close()

print(f'\nпровалено: {len(errs)}')
sys.exit(1 if errs else 0)
