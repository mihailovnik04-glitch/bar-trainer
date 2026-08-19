# -*- coding: utf-8 -*-
"""01_parse.py — data/data.json -> data/drinks.json

Листы с напитками устроены одинаково и БЕЗ объединённых ячеек, структура держится
только на расположении (см. CLAUDE.md):

  A  название напитка — только в первой строке блока, дальше пусто
  B  ингредиент
  C  граммовка; в последней строке блока — выход напитка
  D  способ приготовления; в строке с выходом — правило подачи

Новый блок начинается там, где A непустая, а в предыдущей строке A пустая.
Две непустые A подряд — это перенос названия, части склеиваются через ' / '.
Фото принадлежит блоку, если строка его якоря попадает в диапазон блока;
колонка > 2 означает дополнительное фото (альтернативное украшение).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SHEETS = ['Лонг Дринки', 'Шотики', 'Лимонады и БА',
          'Лимонады с собой (Акция)', 'Горячие', 'Самовывоз']

cells = json.load(open(ROOT / 'data' / 'data.json', encoding='utf-8'))
imgmap = json.load(open(ROOT / 'data' / 'images.json', encoding='utf-8'))


def norm(v):
    """Только обрезка по краям. Двойные пробелы внутри ячейки НЕ схлопываем —
    данные переносятся дословно (железное правило проекта), и 99_verify.py
    сверяет строки посимвольно."""
    return str(v).strip()


def parse_sheet(name):
    rows = {r[0]: [norm(x) for x in r[1:]] for r in cells[name]}
    if not rows:
        return []
    maxr = max(rows)

    def c(r, col):                      # col — 1-based, как в Excel
        row = rows.get(r)
        return row[col - 1] if row and len(row) >= col else ''

    a_rows = [r for r in range(1, maxr + 1) if c(r, 1)]
    starts = [r for r in a_rows if r - 1 not in a_rows]

    blocks = []
    for i, s in enumerate(starts):
        gap = (starts[i + 1] - 1) if i + 1 < len(starts) else maxr
        # хвост из пустых строк в блок не входит: иначе диапазон захватит чужие фото
        end = max((r for r in rows if s <= r <= gap), default=s)

        title = []
        r = s
        while c(r, 1):
            title.append(c(r, 1))
            r += 1

        ing, method, total, serve = [], [], '', ''
        for r in range(s, end + 1):
            b, cc, d = c(r, 2), c(r, 3), c(r, 4)
            if b:
                ing.append([b, cc])
            elif cc:                    # строка без ингредиента, но с числом — это выход
                total = cc
                if d:
                    serve = d
                    d = ''
            if d and d not in method:
                method.append(d)

        photos, extra = [], []
        for im in imgmap.get(name, []):
            if s <= im['row'] <= end:
                (photos if im['col'] <= 2 else extra).append(im['file'])

        blocks.append({'sheet': name, 'name': ' / '.join(title), 'ing': ing,
                       'method': '\n'.join(method), 'total': total, 'serve': serve,
                       'start': s, 'end': end,
                       'photos': photos, 'extra_photos': extra})
    return blocks


out = []
for sh in SHEETS:
    got = parse_sheet(sh)
    out += got
    print(f'  {sh}: {len(got)} блоков')

json.dump(out, open(ROOT / 'data' / 'drinks.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print(f'всего блоков: {len(out)}')
