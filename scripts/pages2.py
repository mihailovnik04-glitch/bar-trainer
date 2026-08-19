# -*- coding: utf-8 -*-
"""Справочные главы: кофе, чай, ПФ, украшения, стандарты подачи."""
import re
from build import esc, img, imgs, cells, sheet_rows, parse_blocks, block_photo, rcard, markup_method
from pages import sec

def escb(s):
    return esc(s).replace('\n', '<br>')

# ------------------------------------------------------------------ КОФЕ
def coffee_html():
    blocks = [b for b in parse_blocks('Кофе') if b['row0'] >= 13 and 'Кол-во кофе' not in b['name']]
    order = ['Эспрессо', 'Эспрессо Двойной', 'Эспрессо 8 гр (только Кофейные)', 'Лунго',
             'Американо 8 гр', 'Американо 15 гр', 'Американо Двойной',
             'Капучино', 'Капучино Двойной', 'Флэт Уайт', 'Латте', 'Латте Двойной',
             'Кофе без кофеина одинарный (ЧАЛДЫ)', 'Кофе без кофеина двойной (ЧАЛДЫ)',
             'Кофе без кофеина одинарный (МОЛОТЫЙ)', 'Кофе без кофеина двойной (МОЛОТЫЙ)']
    bym = {b['name']: b for b in blocks}
    matrix = '''
<div class="page-head"><h2>Кофейная матрица</h2><span>Глава 12 · Кофе</span></div>
<table class="t">
<tr><th>Напиток</th><th>Кофе</th><th>Вода / молоко</th><th>Экстракция</th><th>Выход</th><th>Посуда</th></tr>
<tr><td><b>Эспрессо</b></td><td class="m">15–16 гр</td><td class="m">—</td><td class="m">15–20 сек</td><td class="m">30 мл</td><td>чашка эспрессо</td></tr>
<tr><td><b>Эспрессо 8 гр</b></td><td class="m">8–9 гр</td><td class="m">—</td><td class="m">20–25 сек</td><td class="m">30 мл</td><td>только для кофейных коктейлей</td></tr>
<tr><td><b>Эспрессо двойной</b></td><td class="m">15–16 гр</td><td class="m">—</td><td class="m">20–25 сек</td><td class="m">60 мл</td><td>чашка американо</td></tr>
<tr><td><b>Лунго</b></td><td class="m">8–9 гр</td><td class="m">—</td><td class="m">30–35 сек</td><td class="m">45 мл</td><td>—</td></tr>
<tr><td><b>Американо 8 гр</b></td><td class="m">8–9 гр</td><td class="m">95 мл воды</td><td class="m">30–35 сек</td><td class="m">140 мл</td><td>чашка американо</td></tr>
<tr><td><b>Американо 15 гр</b></td><td class="m">15–16 гр</td><td class="m">110 мл воды</td><td class="m">15–20 сек</td><td class="m">140 мл</td><td>чашка американо</td></tr>
<tr><td><b>Американо двойной</b></td><td class="m">15–16 гр</td><td class="m">180 мл воды</td><td class="m">30–35 сек</td><td class="m">270 мл</td><td>большая цветная чашка</td></tr>
<tr><td><b>Капучино</b></td><td class="m">30 мл эспрессо</td><td class="m">120 мл молока</td><td class="m">20–25 сек</td><td class="m">150 мл</td><td>чашка американо</td></tr>
<tr><td><b>Капучино двойной</b></td><td class="m">60 мл</td><td class="m">240 мл молока</td><td class="m">20–25 сек</td><td class="m">300 мл</td><td>большая цветная чашка</td></tr>
<tr><td><b>Флэт Уайт</b></td><td class="m">60 мл</td><td class="m">100 мл молока</td><td class="m">20–25 сек</td><td class="m">160 мл</td><td>чашка американо</td></tr>
<tr><td><b>Латте</b></td><td class="m">30 мл</td><td class="m">220 мл молока</td><td class="m">—</td><td class="m">250 мл</td><td>цветная чашка</td></tr>
<tr><td><b>Латте двойной</b></td><td class="m">60 мл</td><td class="m">350 мл молока</td><td class="m">—</td><td class="m">410 мл</td><td>Хайбол 460 / Ступенька L 480</td></tr>
</table>
<div class="grid2" style="margin-top:4mm">
<div class="box tint"><div class="lbl">Что повторяется в каждом рецепте</div>
<ul class="clean"><li>Сухой, чистый и <b>горячий</b> холдер</li>
<li>Пролив воды в группе <b>3–5 секунд</b> — выравниваем температуру</li>
<li>Темпер: угол <b>90°</b>, усилие <b>15–20 кг</b></li>
<li>Молоко всегда <b>75–80°</b>, посуда всегда прогрета</li></ul></div>
<div class="box tint"><div class="lbl">Мнемоника молочных</div>
<p style="font-size:8.6pt;line-height:1.55"><b>Капучино 120 · Флэт 100 · Латте 220.</b>
Пена по убыванию: капучино — объём в два раза больше, флэт — «частично увеличенный», латте — почти не увеличиваем.<br>
Двойной = кофе ×2, молоко ×2 (латте — исключение: 350, а не 440, и <b>не отдаётся на вынос</b>).</p></div>
</div>'''

    cards = ['<div class="page-head"><h2>Технология по напиткам</h2><span>Глава 12 · Кофе</span></div>']
    for nm in order:
        b = bym.get(nm)
        if not b: continue
        badges = [(f'{a} {n}'.strip() if n else a, False) for n, a in b['ing']]
        if b['total']: badges.append((b['total'], True))
        cards.append(rcard(nm, badges, b['steps'], block_photo('Кофе', b, col_max=9)))
    cards.append('''<div class="box tint no-break"><div class="lbl">На вынос</div>
    <p style="font-size:8.6pt">Готовим по технологии, переливаем в брендированный бумажный стакан.
    В маленьких стаканчиках — «Карел», «Варяг», «Глинтвейн», «Бинго Бонго», «Сливочное пиво», «Какао с маршмеллоу»;
    в больших — всё остальное. <b>Подачи двойного латте «с собой» нет.</b>
    При заказе двух и более напитков в один чек — картонный холдер (под 2 или 4 стаканчика).</p></div>''')
    return [matrix, '\n'.join(cards)]

# ------------------------------------------------------------------ ЧАЙ
def tea_html():
    R = sheet_rows('Чай ')
    def cell(r, c): return R.get(r, {}).get(c, '').strip()
    taiga = [(cell(r, 2), cell(r, 3)) for r in range(10, 16) if cell(r, 2)]
    taiga_m = ' '.join(cell(r, 4) for r in range(10, 16) if cell(r, 4))
    punch = [(cell(r, 2), cell(r, 3)) for r in range(24, 30) if cell(r, 2)]
    punch_m = ' '.join(cell(r, 4) for r in range(24, 30) if cell(r, 4))
    ph = {i['row']: i['file'] for i in imgs.get('Чай ', [])}

    html = f'''
<div class="page-head"><h2>Заваривание чая</h2><span>Глава 13 · Чай</span></div>
<p class="note" style="margin-bottom:4mm">{escb(cell(1,1))}</p>
<table class="t">
<tr><th>Вид чая</th><th>Дозировка</th><th>Температура</th><th>Ложек «1 tbsp»</th><th>Правило</th></tr>
<tr><td colspan="5" style="background:#F4F1EA"><b>Чёрный</b></td></tr>
<tr><td>Ассам</td><td class="m">10 гр</td><td class="m">100 °C</td><td class="m">2</td>
    <td rowspan="4" style="font-size:7.8pt">Чайник предварительно прогреть горячей водой.<br>Время заваривания — <b>4 минуты</b>.</td></tr>
<tr><td>Эрл Грей</td><td class="m">10 гр</td><td class="m">100 °C</td><td class="m">3</td></tr>
<tr><td>Цейлонский Чабрец</td><td class="m">10 гр</td><td class="m">100 °C</td><td class="m">2</td></tr>
<tr><td>Таёжный Микс</td><td class="m">12 гр</td><td class="m">100 °C</td><td class="m">3</td></tr>
<tr><td>Ассам со свежим чабрецом</td><td class="m">10 гр + 2 гр чабреца</td><td class="m">100 °C</td><td class="m">—</td>
    <td style="font-size:7.8pt">1. Заварить порцию ассама. 2. Опустить внутрь чайника веточку чабреца.</td></tr>
<tr><td colspan="5" style="background:#F4F1EA"><b>Зелёный</b></td></tr>
<tr><td>Молочный Улун</td><td class="m">8 гр</td><td class="m">80 °C</td><td class="m">1</td>
    <td rowspan="3" style="font-size:7.8pt">До погружения заварки опустить в чайник с кипятком <b>кубик льда</b>.</td></tr>
<tr><td>Сенча</td><td class="m">8 гр</td><td class="m">80 °C</td><td class="m">2</td></tr>
<tr><td>Жасмин</td><td class="m">8 гр</td><td class="m">80 °C</td><td class="m">2</td></tr>
<tr><td colspan="5" style="background:#F4F1EA"><b>Тизан и какао</b></td></tr>
<tr><td>Фруктовый Пунш</td><td class="m">15 гр</td><td class="m">100 °C</td><td class="m">2</td>
    <td style="font-size:7.8pt">Все тизаны (без чайного листа) завариваются по правилу чёрного чая.</td></tr>
<tr><td>Какао</td><td class="m">10 гр</td><td class="m">—</td><td class="m">2</td><td></td></tr>
</table>

<div class="grid3" style="margin-top:4mm">
 <div class="mini"><span class="num">10 · 8 · 15</span><b>Дозировки</b><p>Чёрный 10 гр, зелёный 8 гр, тизан 15 гр. Таёжный микс — 12 гр, какао — 10 гр.</p></div>
 <div class="mini"><span class="num">100 / 80</span><b>Температура</b><p>Зелёный заваривается на 20° холоднее и со льдом в чайнике.</p></div>
 <div class="mini"><span class="num">4 / 5</span><b>Время</b><p>Обычный чай — 4 минуты, крафтовые смеси — не менее 5 минут.</p></div>
</div>

<div class="sec" style="margin-top:5mm"><h3><span class="n">·</span>Правильное заваривание</h3>
<table class="t">
<tr><td style="width:33%">{escb(cell(34,1))}</td><td style="width:33%">{escb(cell(34,2))}</td><td>{escb(cell(34,5))}</td></tr>
</table></div>
'''

    craft = f'''
<div class="page-head"><h2>Крафтовые смеси и подача</h2><span>Глава 13 · Чай</span></div>
{rcard('Таёжный Микс Крафт', [('750 мл', True), ('чайник керамика', False), ('настаивать 5 мин', False)],
       [taiga_m], ph.get(8, ''), ing=taiga)}
{rcard('Фруктовый Пунш Крафт', [('750 мл', True), ('чайник керамика', False), ('настаивать 5 мин', False)],
       [punch_m], ph.get(22, ''), ing=punch)}

<div class="sec"><h3><span class="n">·</span>Подача лимона</h3>
<div class="grid2"><div class="box">
<p style="font-size:8.6pt">{escb(cell(47,1))}</p>
<p style="font-size:8.6pt">{escb(cell(47,5))}</p></div>
<div class="gal" style="grid-template-columns:1fr 1fr">
<figure><div class="im">{img(ph.get(48,''))}</div></figure>
<figure><div class="im">{img(ph.get(49,''))}</div></figure></div></div></div>

<div class="sec"><h3><span class="n">·</span>Подача чабреца (тимьяна) и мяты</h3>
<div class="grid2">
<div class="box"><div class="lbl">Чабрец</div><p style="font-size:8.4pt">{escb(cell(58,1))}</p>
<p class="note">{escb(cell(58,5))}</p></div>
<div class="box"><div class="lbl">Мята</div><p style="font-size:8.4pt">{escb(cell(72,1))}</p>
<p class="note">{escb(cell(72,5))}</p></div>
</div>
<div class="gal" style="margin-top:3mm">
<figure><div class="im">{img(ph.get(62,''))}</div><figcaption>Чабрец: убрать лишнее</figcaption></figure>
<figure><div class="im">{img(ph.get(63,''))}</div><figcaption>В чайник — только годные веточки</figcaption></figure>
<figure><div class="im">{img(ph.get(76,''))}</div><figcaption>Листья мяты без соцветий</figcaption></figure>
<figure><div class="im">{img(ph.get(36,''))}</div><figcaption>Подача отдельно на блюдце</figcaption></figure>
</div></div>
'''
    return [html, craft]

# ------------------------------------------------------------------ ПФ
def pf_html():
    keep = ['ПФ Пастила Лимон', 'Сахарная картинка', 'ПФ Ходзича', 'ПФ Пена Кокос', 'ПФ Лимонделло',
            'ПФ Сироп Помело', 'ПФ Вишневый кордиал', 'ПФ Грейпфрутовый Кордиал', 'ПФ Нарезка на сангрию',
            'ПФ Сахарный Сироп', 'ПФ Лайм микс', 'ПФ Микс волшебных специй']
    blocks = {b['name']: b for b in parse_blocks('ПФ')}
    ph = {i['row']: i['file'] for i in imgs.get('ПФ', [])}
    out = ['<div class="page-head"><h2>Полуфабрикаты</h2><span>Глава 14 · ПФ</span></div>',
           '''<p class="note" style="margin-bottom:4mm">ПФ — основа половины меню. Перепутанный полуфабрикат
           ломает сразу несколько напитков, поэтому пропорции здесь важнее, чем где-либо.</p>''']
    for nm in keep:
        b = blocks.get(nm)
        if not b: continue
        badges = []
        if b['total']: badges.append((b['total'], True))
        out.append(rcard(nm, badges, b['steps'], ing=b['ing']))
    shokoreh = blocks.get('На куске помело делаем ровный край. Выделенная часть – не отход, из него получится небольшой кусочек. '
                          'Этот цукат уместно использовать для украшения Памелы (2 шт по 4,5-5 гр) '
                          'Отход после зачистки (30-35%) использовать в ПФ Сироп Помело. '
                          'Цукаты помело приходят разного размера и нарезка может отличаться. '
                          'Главная задача - сделать аккуратные куски по 4,5-5 гр. ПФ Шокорех')
    if shokoreh:
        out.append(rcard('ПФ Шокорех', [('630 мл', True)],
                         ['Смешать пасту Nut Story и горячую воду до полного растворения.',
                          'Допускается использование блендера.'],
                         ing=[('Паста Nut Story', '350 гр'), ('Вода горячая', '350 мл')]))
    R = sheet_rows('ПФ')
    def c(r, col): return R.get(r, {}).get(col, '').strip()
    out.append(f'''<div class="sec no-break"><h3><span class="n">·</span>Нарезка: бамбук и цукаты помело</h3>
<div class="grid2">
<div class="box"><div class="lbl">Бамбуковый лист</div>
<ul class="clean"><li>{escb(c(54,1))}</li><li>{escb(c(54,2))}</li><li>{escb(c(54,3))}</li></ul>
<div class="gal" style="grid-template-columns:1fr 1fr;margin-top:2.5mm">
<figure><div class="im">{img(ph.get(45,''))}</div></figure>
<figure><div class="im">{img([i['file'] for i in imgs.get('ПФ',[]) if i['row']==45 and i['col']==3][0] if [i for i in imgs.get('ПФ',[]) if i['row']==45 and i['col']==3] else '')}</div></figure>
</div></div>
<div class="box"><div class="lbl">Цукаты помело · 5 гр</div>
<ul class="clean"><li>{escb(c(65,1))}</li><li>{escb(c(65,2))}</li><li>{escb(c(75,1))}</li><li>{escb(c(76,1))}</li><li>{escb(c(77,1))}</li></ul>
<div class="gal" style="grid-template-columns:1fr 1fr;margin-top:2.5mm">
<figure><div class="im">{img(ph.get(57,''))}</div></figure>
<figure><div class="im">{img(ph.get(67,''))}</div></figure>
</div></div></div></div>''')

    S = sheet_rows('Сахарный сироп ПФ')
    def s(r, col): return S.get(r, {}).get(col, '').strip()
    sph = [i['file'] for i in imgs.get('Сахарный сироп ПФ', [])]
    out.append(f'''<div class="sec no-break"><h3><span class="n">·</span>Эталон сахарного сиропа</h3>
<div class="grid2">
<div class="box tint"><div class="lbl">{escb(s(1,1))}</div>
<p style="font-size:9pt"><b>{escb(s(1,4) or '500 гр воды и 800 гр сахара')}</b></p>
<p style="font-size:8.4pt"><b>Инвентарь.</b> {escb(s(3,4))}</p>
<p style="font-size:8.4pt"><b>Технология.</b> {escb(s(4,4))}</p></div>
<div class="box"><div class="lbl">Проверка качества</div>
<p style="font-size:8.4pt">{escb(s(6,4))}</p>
<p class="note">{escb(s(8,4))}</p></div></div>
<div class="gal" style="grid-template-columns:1fr 1fr;margin-top:3mm">
{''.join(f'<figure><div class="im">{img(f)}</div></figure>' for f in sph)}
</div></div>''')
    return ['\n'.join(out)]

# ------------------------------------------------------------------ УКРАШЕНИЯ
def garnish_html():
    R = sheet_rows('Украшения')
    rows_ = [1, 17, 33, 51, 67, 83]
    pics = imgs.get('Украшения', [])
    figs = []
    for bi, r0 in enumerate(rows_):
        r1 = rows_[bi + 1] - 1 if bi + 1 < len(rows_) else 98
        for col in (1, 3, 5, 7):
            label = R.get(r0, {}).get(col, '').strip()
            weight = R.get(r0 + 1, {}).get(col + 1, '').strip()
            if not label: continue
            cand = sorted([i for i in pics if r0 <= i['row'] <= r1 and i['col'] == col], key=lambda i: i['row'])
            f = cand[0]['file'] if cand else ''
            label = re.sub(r'\s*\(на фото[^)]*\)', '', label)
            weight = re.sub(r'\s+', ' ', weight)
            figs.append(f'''<figure><div class="im">{img(f, alt=label)}</div>
              <figcaption>{esc(label)}<span class="w">{esc(weight)}</span></figcaption></figure>''')
    T = sheet_rows('Трубочки')
    straws = [T.get(r, {}).get(1, '').strip() for r in (1, 3, 5, 7)]
    sph = imgs.get('Трубочки', [])
    return [f'''
<div class="page-head"><h2>Украшения: вес и вид</h2><span>Глава 15 · Украшения</span></div>
<p class="note" style="margin-bottom:4mm">Украшение — часть рецептуры, а не «на глаз». Ниже — эталонный вид и вес каждого элемента.</p>
<div class="gal">{''.join(figs)}</div>''',
f'''
<div class="page-head"><h2>Трубочки</h2><span>Глава 15 · Украшения</span></div>
<div class="grid2">
<div class="box">
<ul class="clean" style="font-size:9pt">{''.join(f'<li>{esc(s)}</li>' for s in straws if s)}</ul>
<p class="note">Напитки «с собой»: трубочка подаётся в индивидуальной упаковке и в напиток не вставляется.</p>
</div>
<div>{img(sph[0]['file'] if sph else '', cls='', alt='Трубочки')}</div>
</div>''']

# ------------------------------------------------------------------ СТАНДАРТЫ
def standards_html():
    R = sheet_rows('Спец. подачи')
    def c(r, col): return R.get(r, {}).get(col, '').strip()
    ph = {}
    for i in imgs.get('Спец. подачи', []):
        ph.setdefault(i['row'], i['file'])

    liquor = [c(r, 2) for r in range(8, 15) if c(r, 2)]
    likers = [c(r, 2) for r in range(15, 21) if c(r, 2)]
    tops = [(c(r, 1), c(r, 3), c(r, 4)) for r in range(40, 48) if c(r, 1)]
    top_ph = [ph.get(r, '') for r in range(40, 48)]

    p1 = f'''
<div class="page-head"><h2>Стандарты подачи</h2><span>Глава 16 · Стандарты</span></div>

{sec('1', 'Соки и морсы', f"""<div class="box"><p style="font-size:8.8pt">{escb(c(3,4))}</p>
<p style="font-size:8.8pt">{escb(c(5,4))}</p>
<p class="note">Объём {escb(c(2,3))}. Позиции: {escb(c(3,2))}, {escb(c(4,2))}, {escb(c(5,2))}.</p></div>""")}

{sec('2', 'Порционная подача чистого алкоголя', f"""
<table class="t">
<tr><th>Категория</th><th>Позиции</th><th>Порция</th><th>Как подаём</th></tr>
<tr><td><b>Настойки и наливки</b></td><td>{esc(', '.join(x.strip(' -0123456789)') for x in liquor))}</td>
    <td class="m">50 мл</td><td>{escb(c(8,4))}</td></tr>
<tr><td><b>Ликёры и биттеры</b></td><td>{esc(', '.join(x.strip(' -0123456789)') for x in likers))}</td>
    <td class="m">50 мл</td><td>{escb(c(15,4))}</td></tr>
<tr><td><b>Креплёные вина</b></td><td>{escb(c(21,2))}</td><td class="m">75 мл</td><td>{escb(c(21,4))}</td></tr>
</table>
<p class="note"><b>Мнемоника:</b> 50 — настойки и ликёры, 75 — портвейн. Ликёры и биттеры — в <b>замороженный</b> шот,
настойки — в обычный охлаждённый.</p>""")}

{sec('3', 'Спец. подача текилы', f"""
<div class="grid2"><div class="box">
<div class="lbl">Шот · {escb(c(23,2).replace(chr(10)," / "))} — {escb(c(23,3).replace(chr(10)," / "))}</div>
<p style="font-size:8.4pt">{escb(c(23,4))}</p>
<div class="lbl" style="margin-top:3mm">Целая бутылка · {escb(c(28,2).replace(chr(10)," / ").strip(" /"))}</div>
<p style="font-size:8.4pt">{escb(c(28,4))}</p></div>
<div class="gal" style="grid-template-columns:1fr 1fr">
<figure><div class="im">{img(ph.get(23,''))}</div></figure>
<figure><div class="im">{img(ph.get(50,''))}</div></figure></div></div>""")}

{sec('4', 'Кофе и согревающие: посуда и молоко', f"""<div class="box tint">
<ul class="clean"><li>{escb(c(31,4))}</li><li>{escb(c(32,4))}</li><li>{escb(c(34,4))}</li>
<li>{escb(c(36,4))}</li><li>{escb(c(37,4))}</li></ul></div>""")}
'''

    tops_html = ''.join(f'''<figure><div class="im">{img(top_ph[i] if i < len(top_ph) else '')}</div>
        <figcaption>{esc(n)}<span class="w">{esc(a)}</span></figcaption></figure>'''
                        for i, (n, a, _) in enumerate(tops))
    tops_rules = ''.join(f'<tr><td><b>{esc(n)}</b></td><td class="m">{esc(a)}</td><td>{esc(t)}</td></tr>'
                         for n, a, t in tops)
    p2 = f'''
<div class="page-head"><h2>Топинги и напитки с собой</h2><span>Глава 16 · Стандарты</span></div>

{sec('5', 'Подача топингов', f"""<div class="gal" style="margin-bottom:3mm">{tops_html}</div>
<table class="t">{tops_rules}</table>""")}

{sec('6', 'Коктейли и холодные напитки «с собой»', f"""
<div class="box"><p style="font-size:8.6pt">{escb(c(49,4))}</p>
<div class="grid2" style="margin-top:2mm">
<div><div class="lbl">Стакан 0,3 л</div><p style="font-size:8.2pt">{escb(c(51,4))}</p><p style="font-size:8.2pt">{escb(c(55,4))}</p></div>
<div><div class="lbl">Стакан 0,5 л</div><p style="font-size:8.2pt">{escb(c(56,4))}</p></div></div>
<div class="lbl" style="margin-top:2mm">Украшения и трубочки</div>
<p style="font-size:8.2pt">{escb(c(59,4))}</p><p style="font-size:8.2pt">{escb(c(64,4))}</p>
<p class="note">{escb(c(66,4))}</p></div>""")}

{sec('7', 'Кофейные и согревающие «с собой»', f"""
<div class="box"><p style="font-size:8.6pt">{escb(c(68,4))}</p>
<p style="font-size:8.4pt">{escb(c(70,4))}</p><p style="font-size:8.4pt">{escb(c(71,4))}</p>
<div class="lbl" style="margin-top:2mm">Украшения и трубочки</div>
<p style="font-size:8.2pt">{escb(c(73,4))}</p><p class="note">{escb(c(77,4))}</p></div>""")}
'''
    return [p1, p2]
