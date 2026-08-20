# -*- coding: utf-8 -*-
"""Проверка экрана графика на поддельном сервере.

Реальный Supabase для проверки не нужен: запросы к `/rest/v1/...` перехватываются
Playwright и отвечают фикстурой. Фикстура — слепок настоящих строк из базы
(`data/sched_fixture.json`), чтобы формы данных были ровно те же, что в бою:
104 смены за вторую половину августа, восемь сотрудников, три точки.

    python scripts/95_sched_test.py            прогон
    python scripts/95_sched_test.py --shot      + снимок экрана в build/
"""
import sys, json, pathlib, urllib.parse
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / 'build' / 'app' / 'index.html'
FIX = json.load(open(ROOT / 'data' / 'sched_fixture.json', encoding='utf-8'))
SHOT = '--shot' in sys.argv
errs = []


def check(name, cond, extra=''):
    print(('  ok  ' if cond else 'FAIL  ') + name + (('  ' + extra) if extra and not cond else ''))
    if not cond:
        errs.append(name)


def handle(route, request):
    """Отдаём фикстуру по имени таблицы из пути. Фильтры PostgREST не разбираем:
    в фикстуре ровно один период, и лишнего в ней нет."""
    path = urllib.parse.urlparse(request.url).path
    table = path.rsplit('/', 1)[-1]
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps(FIX.get(table, []), ensure_ascii=False))


with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    js_errors = []
    pg.on('console', lambda m: js_errors.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: js_errors.append(str(e)))

    # Сессия кладётся до загрузки скрипта: иначе приложение покажет экран входа.
    # uid совпадает с одним из staff.user_id — если он там проставлен.
    pg.add_init_script('''
      try{ localStorage.setItem('barquiz.auth', JSON.stringify(
        {token:'t', refresh:'r', uid:'test-uid', mail:'test@local',
         role:'owner', cat:3, dept:'bar', venue:'ТС-45', exp:Date.now()+36e5})); }catch(e){}
    ''')
    pg.route('**/rest/v1/**', handle)
    pg.route('**/auth/v1/**', lambda r: r.fulfill(status=200, content_type='application/json',
                                                  body='{"access_token":"t","refresh_token":"r","expires_in":3600}'))
    pg.goto(APP.as_uri())
    pg.wait_for_timeout(400)

    check('главная отрисована', pg.locator('#home').is_visible())
    pg.click('[data-mode="sched"]')
    pg.wait_for_timeout(600)

    check('экран графика открылся', pg.locator('#sched').is_visible())
    check('заголовок периода заполнен', pg.locator('#schTitle').inner_text().strip() not in ('', '—'),
          pg.locator('#schTitle').inner_text())
    rows = pg.locator('.schgrid tbody tr').count()
    check('строк по числу сотрудников', rows == len(FIX['staff']), f'{rows} против {len(FIX["staff"])}')
    cols = pg.locator('.schgrid thead th').count() - 1        # минус колонка имён
    check('колонок по числу дней', cols == 16, str(cols))      # 16–31 августа

    # Часы: сумма по строкам сетки должна совпасть с суммой в фикстуре.
    want = sum(s['hours'] or 0 for s in FIX['shifts'] if s['layer'] == 'plan')
    got = pg.evaluate('''() => [...document.querySelectorAll('.schgrid tbody .nm span')]
        .reduce((a,e)=>a+parseInt(e.textContent)||a, 0)''')
    check('часы сходятся с базой', got == want, f'{got} против {want}')

    filled = pg.locator('.schgrid td.c.work, .schgrid td.c.off, .schgrid td.c.away').count()
    check('клетки заполнены', filled > 60, str(filled))
    check('выходные подсвечены', pg.locator('.schgrid td.c.off').count() > 0)
    check('прилипшая колонка имён', pg.evaluate(
        "getComputedStyle(document.querySelector('.schgrid .nm')).position") == 'sticky')

    # Листание полумесяцев: заголовок обязан смениться.
    before = pg.locator('#schTitle').inner_text()
    pg.click('#schPrev'); pg.wait_for_timeout(400)
    check('листание назад меняет период', pg.locator('#schTitle').inner_text() != before,
          pg.locator('#schTitle').inner_text())
    pg.click('#schNext'); pg.wait_for_timeout(400)
    check('листание вперёд возвращает', pg.locator('#schTitle').inner_text() == before)

    if SHOT:
        pg.screenshot(path=str(ROOT / 'build' / 'sched.png'), full_page=True)
        print('  снимок: build/sched.png')

    check('нет ошибок в консоли', not js_errors, ' | '.join(js_errors[:3]))
    b.close()

print(f'\nпровалено: {len(errs)}')
sys.exit(1 if errs else 0)
