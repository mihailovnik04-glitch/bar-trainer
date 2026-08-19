# -*- coding: utf-8 -*-
"""Проверка входа и синхронизации на поддельном Supabase."""
import json, pathlib, re, sys
from playwright.sync_api import sync_playwright

APP = pathlib.Path.cwd() / 'build' / 'app' / 'index.html'
html = APP.read_text(encoding='utf-8')
# Подменяем адрес проекта на поддельный: тест проверяет логику входа, а не Supabase,
# и не должен зависеть от того, заполнен ли data/auth.json.
import re as _re
patched, n = _re.subn(r'const SB = \{[^}]*\};',
                      'const SB = {"url":"https://fake.supabase.co","key":"testkey"};', html)
assert n == 1, 'не найден конфиг SB в сборке'
tmp = APP.parent / '_auth_test.html'
tmp.write_text(patched, encoding='utf-8')

errs, calls = [], []


def check(name, cond, extra=''):
    print(('  ok  ' if cond else 'FAIL  ') + name + (('  ' + str(extra)) if not cond else ''))
    if not cond:
        errs.append(name)


with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    js_err = []
    pg.on('pageerror', lambda e: js_err.append(str(e)))

    stored = {'data': None}

    def handle(route):
        req = route.request
        calls.append(req.method + ' ' + req.url)
        if '/auth/v1/token' in req.url:
            body = json.loads(req.post_data or '{}')
            if body.get('password') == 'good' or body.get('refresh_token'):
                return route.fulfill(status=200, content_type='application/json', body=json.dumps({
                    'access_token': 'tok', 'refresh_token': 'ref', 'expires_in': 3600,
                    'user': {'id': 'uid-1', 'email': body.get('email', 'a@b.c')}}))
            return route.fulfill(status=400, content_type='application/json',
                                 body=json.dumps({'error_description': 'Invalid login credentials'}))
        if '/rest/v1/bar_progress' in req.url:
            if req.method == 'GET':
                rows = [{'data': stored['data']}] if stored['data'] else []
                return route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))
            stored['data'] = json.loads(req.post_data or '{}').get('data')
            return route.fulfill(status=201, content_type='application/json', body='[]')
        route.fulfill(status=404, body='')

    pg.route('https://fake.supabase.co/**', handle)
    pg.goto(tmp.as_uri())
    pg.wait_for_timeout(400)

    check('без сессии показан экран входа', pg.locator('#login').is_visible())
    check('приложение спрятано', not pg.locator('#home').is_visible())

    pg.fill('#logMail', 'mihailov.nik04@mail.ru')
    pg.fill('#logPass', 'wrong')
    pg.click('#logGo'); pg.wait_for_timeout(400)
    check('неверный пароль не пускает', pg.locator('#login').is_visible())
    check('видно сообщение об ошибке', 'Неверная почта или пароль' in pg.locator('#logErr').inner_text())

    pg.fill('#logPass', 'good')
    pg.click('#logGo'); pg.wait_for_timeout(500)
    check('верный пароль пускает', pg.locator('#home').is_visible())
    check('почта видна на главной', 'mihailov' in pg.locator('#homeFoot').inner_text())

    # прогресс уходит в базу
    pg.evaluate("store.errors['test-id']=3; store.fav['Аперол Спритц']=1; save()")
    pg.wait_for_timeout(4600)
    check('прогресс отправлен в базу', stored['data'] is not None
          and stored['data'].get('errors', {}).get('test-id') == 3)

    # перезагрузка: сессия сохранилась, прогресс подтянулся
    pg.evaluate("localStorage.removeItem('barquiz.v3')")
    pg.reload(); pg.wait_for_timeout(700)
    check('после перезагрузки вход не нужен', pg.locator('#home').is_visible())
    check('прогресс подтянулся из базы', pg.evaluate("store.errors['test-id']") == 3)
    check('избранное подтянулось', pg.evaluate("!!store.fav['Аперол Спритц']"))

    # выход
    pg.click('#logout'); pg.wait_for_timeout(300)
    check('выход возвращает на экран входа', pg.locator('#login').is_visible())

    check('нет ошибок в консоли', not js_err, ' | '.join(js_err[:2]))
    b.close()

tmp.unlink()
print()
print('запросов к серверу:', len(calls))
print('провалено:', len(errs))
sys.exit(1 if errs else 0)
