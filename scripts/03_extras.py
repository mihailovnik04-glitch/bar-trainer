# -*- coding: utf-8 -*-
"""Разбор листов «Кофе», «Чай » и «ПФ» -> data/extras.json.

Структура у всех трёх листов та же, что у листов с коктейлями: объединённых ячеек нет,
блок держится на расположении. Колонка A — название блока (только в первой строке),
B — ингредиент, C — граммовка (или «Выход: N мл»), D — шаги приготовления.

Ничего не переписываем: названия, дозы и шаги переносятся дословно.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cells = json.load(open(ROOT / 'data' / 'data.json', encoding='utf-8'))


def rows_of(sheet):
    """{номер строки: [A, B, C, D, ...]}"""
    return {r[0]: [c.strip() for c in r[1:]] for r in cells[sheet]}


# ---------------------------------------------------------------- кофе
# Оглавление на строках 7–11 перечисляет напитки, дальше идут сами блоки.
# Заголовок блока — строка, где непустая только колонка A.
BUTTON = re.compile(r'кнопку пролива с изображением ([^.]+)')
EXTRACT = re.compile(r'[Вв]ремя экстракции\s*(\d+\s*-\s*\d+)\s*сек')
MILK_T = re.compile(r'до температуры\s*(\d+\s*-\s*\d+)\s*°')


def parse_coffee():
    rows = rows_of('Кофе')
    keys = sorted(rows)
    blocks, cur = [], None
    for r in keys:
        if r < 13:
            continue
        a, b, c, d = (rows[r] + ['', '', '', ''])[:4]
        head = a and not b and not c and not d
        if head:
            # «Кофе без кофеина одинарный » + «(ЧАЛДЫ)» — название на две строки
            if cur and not cur['ing'] and not cur['steps']:
                cur['name'] = (cur['name'] + ' ' + a).strip()
                continue
            cur = {'name': a, 'ing': [], 'total': '', 'steps': []}
            blocks.append(cur)
            continue
        if cur is None:
            continue
        if a and b:                       # вторая строка названия и сразу состав
            cur['name'] = (cur['name'] + ' ' + a).strip()
        if c.startswith('Выход'):
            cur['total'] = c.split(':', 1)[1].strip()
        elif b and c:
            cur['ing'].append([b, c])
        if d:
            cur['steps'].append(d)
    out = []
    for x in blocks:
        if not x['ing']:
            continue
        text = ' '.join(x['steps'])
        m = BUTTON.search(text)
        x['button'] = m.group(1).strip() if m else ''
        m = EXTRACT.search(text)
        x['extract'] = m.group(1).replace(' ', '') + ' сек' if m else ''
        m = MILK_T.search(text)
        x['milk'] = m.group(1).replace(' ', '') + ' °C' if m else ''
        x['method'] = '\n'.join(x['steps'])
        out.append(x)
    return out


# ---------------------------------------------------------------- чай
# Простые сорта — одна строка: A вид, B дозировка, C температура, D ложек.
# Крафтовые смеси — блок: A название, дальше строки B/C с составом.
GROUPS = {'Черный', 'Зеленый', 'Тизан', 'Какао*'}


def parse_tea():
    rows = rows_of('Чай ')
    simple, mixes, cur = [], [], None
    for r in sorted(rows):
        if r < 3 or r > 32:
            continue
        a, b, c, d = (rows[r] + ['', '', '', ''])[:4]
        if a and a.strip() in GROUPS:
            cur = None
            continue
        if a and b and 'гр' in b:                       # обычный сорт
            cur = None
            # «Таежный Микс (до обнуления остатков использовать…)» — в названии сидит
            # примечание на полстроки. В вопросах показываем короткое имя, полное
            # остаётся рядом и попадает в карточку.
            short = a.split('(')[0].strip().rstrip('*').strip()
            simple.append({'name': short or a.strip(), 'full': a.strip(),
                           'dose': b, 'temp': c, 'spoons': d})
        elif a and not b:                               # начало крафтовой смеси
            cur = {'name': a, 'ing': [], 'method': ''}
            mixes.append(cur)
        elif cur is not None and b and c:
            cur['ing'].append([b, c])
            if d:
                cur['method'] = (cur['method'] + '\n' + d).strip()
    return {'simple': simple, 'mixes': [m for m in mixes if m['ing']]}


# ---------------------------------------------------------------- ПФ
# A — название заготовки, B/C — состав, строка с пустыми A и B и заполненной C — выход.
def parse_pf():
    rows = rows_of('ПФ')
    blocks, cur = [], None
    for r in sorted(rows):
        a, b, c, d = (rows[r] + ['', '', '', ''])[:4]
        if a and (b or c or d) or (a and not b and not c and not d):
            if a and not b and not c:
                cur = {'name': a, 'ing': [], 'total': '', 'method': ''}
                blocks.append(cur)
                if d:
                    cur['method'] = d
                continue
            if a:
                cur = {'name': a, 'ing': [], 'total': '', 'method': ''}
                blocks.append(cur)
        if cur is None:
            continue
        if b and c:
            cur['ing'].append([b, c])
        elif not a and not b and c:
            cur['total'] = c
        if d:
            cur['method'] = (cur['method'] + '\n' + d).strip()
    # На листе попадаются строки-инструкции («Бамбуковый лист порезать пополам…»),
    # они выглядят как заголовок блока. Отсекаем по длине: у настоящих заготовок
    # название короткое.
    return [x for x in blocks if x['ing'] and len(x['name']) <= 40]


# ---------------------------------------------------------------- подача
# Лист «Спец. подачи»: заголовки разделов капсом, строки подачи — A название,
# C объём или количество, D правило. Берём только то, где есть измеримая величина.
SECTION = re.compile(r'^[А-ЯЁ \d.,"/-]{6,}$')


# В какой посуде выносить — написано внутри правила («налить в шот», «на цветном
# кофейном блюдце»). Отдельного поля нет, поэтому ищем известные названия по тексту.
# Список закрытый: ничего не додумываем, если ни одно не встретилось — посуду не пишем.
WARE = ['порто гласс', 'замороженный шот', 'кружке эспрессо', 'цветном кофейном блюдце',
        'графине без ручки 1,18л', 'индивидуальной упаковке', 'шот']
WARE_NAME = {'кружке эспрессо': 'кружка эспрессо',
             'цветном кофейном блюдце': 'цветное кофейное блюдце',
             'графине без ручки 1,18л': 'графин без ручки 1,18 л',
             'индивидуальной упаковке': 'индивидуальная упаковка'}


def ware_of(text):
    low = (text or '').lower()
    for w in WARE:                      # длинные варианты стоят раньше короткого «шот»
        if w in low:
            return WARE_NAME.get(w, w)
    return ''


def parse_serve():
    rows = rows_of('Спец. подачи')
    out, section = [], ''
    for r in sorted(rows):
        a, b, c, d = (rows[r] + ['', '', '', ''])[:4]
        if a and SECTION.match(a) and not c:
            section = a.strip().rstrip(' .')
            continue
        name = a or b
        if not name or not c:
            continue
        out.append({'name': name.strip(), 'amount': c.strip(), 'section': section,
                    'rule': d.strip(), 'ware': ware_of(d)})
    return out


# ---------------------------------------------------------------- трубочки
def parse_straws():
    rows = rows_of('Трубочки')
    out = []
    for r in sorted(rows):
        a = (rows[r] + [''])[0]
        if not a:
            continue
        m = re.match(r'^\d+\.\s*(.+?)\s*-\s*(.+)$', a)
        if m:
            out.append({'name': m.group(1).strip(), 'rule': m.group(2).strip()})
        else:
            out.append({'name': a.strip(' .0123456789'), 'rule': ''})
    return out


# ---------------------------------------------------------------- сахарный сироп
def parse_sugar():
    rows = rows_of('Сахарный сироп ПФ')
    return [{'name': (rows[r] + ['', ''])[0], 'text': (rows[r] + ['', ''])[1]}
            for r in sorted(rows) if (rows[r] + ['', ''])[0]]


data = {'coffee': parse_coffee(), 'tea': parse_tea(), 'pf': parse_pf(),
        'serve': parse_serve(), 'straws': parse_straws(), 'sugar': parse_sugar()}
json.dump(data, open(ROOT / 'data' / 'extras.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('кофе:', len(data['coffee']), '· чай:', len(data['tea']['simple']),
      '+ смесей', len(data['tea']['mixes']), '· ПФ:', len(data['pf']))
for x in data['coffee']:
    print(f"  {x['name'][:34]:34} {len(x['ing'])} ингр · выход {x['total'] or '—':9} "
          f"кнопка: {x['button'][:28] or '—'} · {x['extract'] or '—'}")
for x in data['pf']:
    print(f"  ПФ {x['name'][:32]:32} {len(x['ing'])} ингр · выход {x['total'] or '—'}")
print('подача:', len(data['serve']), '· с посудой:',
      sum(1 for x in data['serve'] if x['ware']), '· трубочки:', len(data['straws']),
      '· сироп:', len(data['sugar']))
for x in data['serve']:
    print(f"  {x['name'][:40]:40} {x['amount'][:22]:22} [{x['section'][:26]}]")
