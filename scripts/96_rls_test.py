# -*- coding: utf-8 -*-
"""Проверка RLS-политик графика прямо в базе.

Экранный тест (95_sched_test.py) работает на поддельном сервере и политики не трогает
вовсе — а именно в них прячется самая дорогая ошибка: старший не может выкатить график,
или наоборот бармен правит чужие смены. Поэтому здесь мы влезаем в Postgres под ролью
`authenticated` с подставленным JWT и смотрим, что реально разрешено.

Проверяются три роли: старший бармен, обычный бармен и посторонний аккаунт без карточки.
Все проверки идут внутри транзакции с ROLLBACK — боевые данные не меняются.

    SUPABASE_TOKEN=sbp_… python scripts/96_rls_test.py
"""
import os, sys, json, urllib.request

PROJECT = 'bprfxixyqonjboxyrnyc'
TOKEN = os.environ.get('SUPABASE_TOKEN', '')
if not TOKEN:
    sys.exit('Нужен токен: SUPABASE_TOKEN=sbp_… python scripts/96_rls_test.py')

errs = []


def sql(q):
    req = urllib.request.Request(
        f'https://api.supabase.com/v1/projects/{PROJECT}/database/query',
        data=json.dumps({'query': q}).encode('utf-8'),
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json',
                 'User-Agent': 'curl/8.4.0'}, method='POST')
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        e.body = e.read().decode()[:400]
        raise


def check(name, cond, extra=''):
    print(('  ok  ' if cond else 'FAIL  ') + name + (('  ' + extra) if extra and not cond else ''))
    if not cond:
        errs.append(name)


# Подставляем JWT так же, как это делает PostgREST: роль authenticated плюс claims.
# Подготовка (setup) обязана идти ДО переключения роли: под authenticated в auth.users
# не пишут, и RLS уже действует.
def as_user(uid, role, setup, body):
    claims = json.dumps({'sub': uid, 'role': 'authenticated',
                         'app_metadata': {'role': role}}).replace("'", "''")
    return f"""
    begin;
      {setup}
      set local role authenticated;
      set local request.jwt.claims = '{claims}';
      {body}
    rollback;
    """


def one(q):
    r = sql(q)
    return r[0] if r else {}


print('готовим двух подопытных сотрудников (в транзакции, боевые данные не меняются)')

# Берём реальные строки, но подставляем выдуманные uid: реальные аккаунты трогать незачем.
venue = one("select id from public.venues where is_own limit 1")['id']
period = one("select id, state from public.periods order by year desc, month desc, half desc limit 1")
staff = sql("select id, name from public.staff order by sort limit 2")
SENIOR, PLAIN = staff[0]['id'], staff[1]['id']
UID_S, UID_P, UID_X = ('11111111-1111-1111-1111-111111111111',
                       '22222222-2222-2222-2222-222222222222',
                       '33333333-3333-3333-3333-333333333333')

# Подопытные uid должны существовать в auth.users — на staff.user_id висит внешний ключ.
setup = f"""
  insert into auth.users (instance_id, id, aud, role, email, created_at, updated_at)
  values ('00000000-0000-0000-0000-000000000000','{UID_S}','authenticated','authenticated',
          'rls-senior@test.local', now(), now()),
         ('00000000-0000-0000-0000-000000000000','{UID_P}','authenticated','authenticated',
          'rls-plain@test.local', now(), now())
  on conflict (id) do nothing;
  update public.staff set user_id='{UID_S}', sched_role='senior' where id='{SENIOR}';
  update public.staff set user_id='{UID_P}', sched_role='bartender' where id='{PLAIN}';
"""


def run(uid, role, body):
    return sql(as_user(uid, role, setup, body))


day = '2099-01-01'                      # дата вне любых боевых периодов
ins = ("insert into public.shifts (period_id, staff_id, venue_id, day, layer, kind, start_h, end_h) "
       f"values ('{period['id']}', '%s', '{venue}', '{day}', '%s', 'work', 16, 4)")

print()
print('старший бармен')
r = run(UID_S, 'staff', "select public.is_boss() as b, public.my_venue() as v;")
check('распознан как старший', r[0]['b'] is True)
check('видит свою точку', r[0]['v'] == venue)
r = run(UID_S, 'staff', (ins % (PLAIN, 'plan')) + " ; select count(*) n from public.shifts where day='%s';" % day)
check('ставит смену в график чужому', r[0]['n'] == 1, str(r))
r = run(UID_S, 'staff', f"update public.periods set state='published' where id='{period['id']}'"
                        f" ; select state from public.periods where id='{period['id']}';")
check('выкатывает график', r[0]['state'] == 'published', str(r))
r = run(UID_S, 'staff', f"update public.staff set category=3 where id='{PLAIN}'"
                        f" ; select category from public.staff where id='{PLAIN}';")
check('правит категорию сотрудника', r[0]['category'] == 3, str(r))

print()
print('обычный бармен')
r = run(UID_P, 'staff', "select public.is_boss() as b;")
check('не начальник', r[0]['b'] is False)
try:
    run(UID_P, 'staff', ins % (PLAIN, 'plan'))
    check('НЕ может писать в график', False, 'запись прошла, а не должна была')
except urllib.error.HTTPError:
    check('НЕ может писать в график', True)
r = run(UID_P, 'staff', (ins % (PLAIN, 'wish')) + " ; select count(*) n from public.shifts where day='%s';" % day)
check('пишет своё пожелание', r[0]['n'] == 1, str(r))
try:
    run(UID_P, 'staff', ins % (SENIOR, 'wish'))
    check('НЕ может писать чужое пожелание', False, 'запись прошла, а не должна была')
except urllib.error.HTTPError:
    check('НЕ может писать чужое пожелание', True)
# UPDATE при отказе не бросает ошибку — RLS просто не показывает строку, и апдейт
# задевает ноль строк. Поэтому проверяем результат, а не исключение.
r = run(UID_P, 'staff', f"update public.staff set sched_role='senior' where id='{PLAIN}'"
                        f" ; select sched_role from public.staff where id='{PLAIN}';")
check('НЕ может назначить себя старшим', r[0]['sched_role'] == 'bartender', str(r))
r = run(UID_P, 'staff', f"update public.periods set state='published' where id='{period['id']}'"
                        f" ; select state from public.periods where id='{period['id']}';")
check('НЕ может выкатить график', r[0]['state'] == period['state'], str(r))
# Читать разрешено всё: заказчик решил, что видно и чужие пожелания, и черновик.
r = run(UID_P, 'staff', "select count(*) n from public.shifts;")
check('видит весь график точки', r[0]['n'] > 100, str(r))

print()
print('посторонний аккаунт без карточки сотрудника')
r = run(UID_X, 'staff', "select public.is_boss() as b, public.my_venue() as v;")
check('не начальник', r[0]['b'] is False)
check('точки не видит', r[0]['v'] is None)
r = run(UID_X, 'staff', "select count(*) n from public.shifts;")
check('чужой график не читает', r[0]['n'] == 0, str(r))

print()
print('владелец без карточки сотрудника')
r = run(UID_X, 'owner', "select public.is_boss() as b;")
check('распознан как начальник', r[0]['b'] is True)
r = run(UID_X, 'owner', "select count(*) n from public.shifts;")
check('видит график всех точек', r[0]['n'] > 100, str(r))

print(f'\nпровалено: {len(errs)}')
sys.exit(1 if errs else 0)
