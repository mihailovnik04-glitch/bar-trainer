# -*- coding: utf-8 -*-
"""Прогон тренажёра в headless-браузере: экраны, ввод, избранное, продолжение сессии.

Сборка с включённым входом (data/auth.json заполнен) начинается с экрана логина,
поэтому тест сначала выключает гейт: проверяем интерфейс, а не Supabase — для входа
есть отдельный 98_auth_test.py на поддельном сервере.
"""
import sys, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve()
APP = pathlib.Path.cwd() / 'build' / 'app' / 'index.html'
errs = []

def check(name, cond, extra=''):
    print(('  ok  ' if cond else 'FAIL  ') + name + (('  ' + extra) if extra and not cond else ''))
    if not cond: errs.append(name)

with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={'width': 390, 'height': 844})
    js_errors = []
    pg.on('console', lambda m: js_errors.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: js_errors.append(str(e)))
    # гейт входа выключаем до загрузки скрипта: подсовываем готовую сессию
    pg.add_init_script('''
      try{ localStorage.setItem('barquiz.auth', JSON.stringify(
        {token:'t', refresh:'r', uid:'test', mail:'test@local', exp:Date.now()+36e5})); }catch(e){}
    ''')
    pg.route('**/*.supabase.co/**', lambda r: r.fulfill(status=200,
             content_type='application/json', body='[]'))
    pg.goto(APP.as_uri())
    pg.wait_for_timeout(500)

    check('главная отрисована', pg.locator('#home').is_visible())
    check('банк загружен', pg.evaluate('BANK.length') > 900, str(pg.evaluate('BANK.length')))

    # --- справочник: виды, избранное, посуда
    pg.click('[data-mode="kb"]'); pg.wait_for_timeout(200)
    check('база знаний открылась', pg.locator('#kb').is_visible())
    check('разделы базы знаний на месте', pg.locator('#kbList .mode').count() >= 3)
    pg.click('[data-kbgo="tech"]'); pg.wait_for_timeout(250)
    check('технологические карты открылись', pg.locator('#ref').is_visible())
    check('чипсы видов есть', pg.locator('#refSheet .chip').count() > 5)
    pg.click('#refSheet [data-sheet="Шотики"]'); pg.wait_for_timeout(150)
    check('фильтр по виду работает', pg.locator('.rrow').count() in range(5, 15),
          str(pg.locator('.rrow').count()))
    pg.locator('.rrow .star').first.click(); pg.wait_for_timeout(100)
    check('коктейль в избранном', pg.evaluate('Object.keys(store.fav).length') == 1)
    pg.click('#refSheet [data-fav-filter]'); pg.wait_for_timeout(150)
    check('фильтр «только избранное»', pg.locator('.rrow').count() == 1,
          str(pg.locator('.rrow').count()))
    pg.click('#refSheet [data-fav-filter]')
    pg.click('#refSort [data-sort="glass"]'); pg.wait_for_timeout(150)
    check('справочник посуды', pg.locator('.gcard').count() > 10, str(pg.locator('.gcard').count()))
    pg.click('#refSort [data-sort="ch"]'); pg.wait_for_timeout(100)
    pg.click('#refSheet [data-sheet="all"]'); pg.wait_for_timeout(100)
    pg.locator('.rrow .t').first.click(); pg.wait_for_timeout(300)
    check('карточка рецепта открылась', pg.locator('#modal.on').count() == 1)
    check('в карточке есть звезда', pg.locator('#sheetCard [data-fav]').count() == 1)
    pg.click('#clsRec'); pg.wait_for_timeout(300)
    pg.click('#ref .scrhead .back'); pg.wait_for_timeout(200)
    pg.click('#kb .scrhead .back'); pg.wait_for_timeout(200)

    # --- база вопросов
    pg.click('[data-mode="qbase"]'); pg.wait_for_timeout(300)
    check('база вопросов открылась', pg.locator('#qbase').is_visible())
    n_all = pg.locator('.qrow').count()
    pg.click('#qbCat [data-cat="glass"]'); pg.wait_for_timeout(200)
    check('фильтр по теме', 0 < pg.locator('.qrow').count() < n_all)
    pg.locator('.qrow .star').first.click(); pg.wait_for_timeout(100)
    check('вопрос в избранном', pg.evaluate('Object.keys(store.favQ).length') == 1)
    pg.click('#qbase .scrhead .back'); pg.wait_for_timeout(200)

    # --- настройка тренировки
    pg.click('[data-mode="setup"]'); pg.wait_for_timeout(300)
    check('экран настройки', pg.locator('#setup').is_visible())
    n_all = int(pg.evaluate('trainPool(OPT).length'))
    check('пул вопросов набран', n_all > 300, str(n_all))
    pg.click('#setSheet [data-sheet="Горячие"]'); pg.wait_for_timeout(200)
    n_hot = int(pg.evaluate('trainPool(OPT).length'))
    check('фильтр вида в тренировке', 0 < n_hot < n_all, f'{n_hot} из {n_all}')
    pg.click('#setPool [data-pool="fav"]'); pg.wait_for_timeout(200)
    pg.click('#setSheet [data-sheet="all"]'); pg.wait_for_timeout(200)
    check('режим «избранное»', 0 < int(pg.evaluate('trainPool(OPT).length')) < n_all)
    pg.click('#setPool [data-pool="all"]'); pg.wait_for_timeout(150)

    # дедуп: в пуле не должно быть двух вопросов на одну строку
    dups = pg.evaluate('''(()=>{const l=trainPool(OPT);const s=new Set();let d=0;
      for(const q of l){const k=dedupKey(q); if(s.has(k)) d++; s.add(k);} return d;})()''')
    check('нет дублей в сессии', dups == 0, str(dups))

    # --- сама тренировка
    pg.click('#setGo'); pg.wait_for_timeout(400)
    check('тренировка началась', pg.locator('#quiz').is_visible())

    # проходим 12 вопросов: числовые вводим падом, выборочные — первой кнопкой
    seen_pad = seen_opt = seen_fill = 0
    for i in range(12):
        pg.wait_for_timeout(120)
        if pg.locator('#numbox').count():
            seen_pad += 1
            if pg.locator('#ftab').count(): seen_fill += 1
            # правильный ответ прямо из состояния — проверяем зачёт, а не угадывание
            ok = pg.evaluate('''(()=>{const q=S.list[S.k];
              const vals = q.t==='mfill' ? q.a : [q.a];
              PAD.vals = vals.map(v=>String(v).replace('.',','));
              PAD.i = PAD.n-1; submitNum(); return S.ans[q.id].ok;})()''')
            check(f'числовой ответ #{i} засчитан', ok is True)
        elif pg.locator('.opt').count():
            seen_opt += 1
            pg.evaluate('''(()=>{const q=S.list[S.k];
              document.querySelectorAll('.opt')[q.ai].click();})()''')
        else:
            check(f'вопрос #{i} отрисован', False, pg.locator('#quiz').inner_text()[:80])
            break
        pg.wait_for_timeout(700)
    check('встречались вопросы с вводом', seen_pad > 0, str(seen_pad))
    check('встречались вопросы с выбором', seen_opt > 0, str(seen_opt))

    # --- шаг назад
    k = pg.evaluate('S.k')
    pg.click('#prev'); pg.wait_for_timeout(300)
    check('шаг назад работает', pg.evaluate('S.k') == k - 1)
    check('назад показывает разбор', pg.locator('#fb.show').count() == 1)

    # --- ошибка возвращается в ближайшие 50
    before = pg.evaluate('S.list.length')
    pg.evaluate('''(()=>{S.k = S.list.length-1; renderQ();})()''')
    pg.wait_for_timeout(200)
    grew = pg.evaluate('''(()=>{const q=S.list[S.k];
      const n0=S.list.length;
      if(q.t==='num'||q.t==='fill'||q.t==='mfill'){ PAD.vals=PAD.vals.map(()=>'99999'); PAD.i=PAD.n-1; submitNum(); }
      else { document.querySelectorAll('.opt')[(q.ai+1)%4].click(); }
      return S.list.length>n0;})()''')
    check('ошибка переспрашивается позже', grew is True)

    # --- сохранение и продолжение сессии
    pg.wait_for_timeout(300)
    pg.evaluate('saveSession()')
    check('сессия сохранена', pg.evaluate('!!JSON.parse(localStorage.getItem("barquiz.v3")).sess'))
    pg.reload(); pg.wait_for_timeout(500)
    pg.click('[data-mode="setup"]'); pg.wait_for_timeout(300)
    check('предложено продолжить', pg.locator('#resGo').count() == 1)
    pg.click('#resGo'); pg.wait_for_timeout(400)
    check('сессия продолжилась', pg.locator('#quiz').is_visible() and pg.evaluate('S.k') > 0)

    # --- экзамен: выхода нет никогда
    pg.evaluate('store.showTotal=true; save()')
    pg.evaluate('start("exam")'); pg.wait_for_timeout(400)
    tot = pg.evaluate('''(()=>{for(let i=0;i<S.list.length;i++){ if(S.list[i].t==='fill'||S.list[i].t==='mfill'){
        S.k=i; renderQ(); return document.querySelector('#ftab .tot')?1:0; } } return -1;})()''')
    check('на экзамене выход скрыт', tot in (0, -1), str(tot))
    pg.evaluate('S.mode="train"; renderQ()'); pg.wait_for_timeout(200)
    tot2 = pg.evaluate("document.querySelector('#ftab .tot')?1:0")
    check('в тренировке выход показан', tot2 == 1)

    check('нет ошибок в консоли', not js_errors, ' | '.join(js_errors[:3]))
    b.close()

print()
print('провалено:', len(errs))
sys.exit(1 if errs else 0)
