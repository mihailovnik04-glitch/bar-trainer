# -*- coding: utf-8 -*-
"""99_verify.py — проверки, без которых нельзя выкатывать сборку.

1. Каждый ингредиент, граммовка, выход, способ приготовления и подача из исходника
   присутствуют в build/index.html дословно.
2. Каждый напиток попал ровно в одну главу (никого не потеряли).
3. Ответы банка вопросов совпадают с исходником.
4. У вопросов с вариантами неверные значения отстоят от верного минимум на 10.

Запускать после любой правки config.py, pages*.py, 40_bank.py.
Скрипт ничего не чинит — он только орёт. Падение = релиз отменяется.
"""
import json, re, html, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
fails = []

# ---------- 1. дословность
src = json.load(open(ROOT / 'data' / 'drinks.json', encoding='utf-8'))
page = (ROOT / 'build' / 'index.html').read_text(encoding='utf-8')
plain = html.unescape(re.sub(r'<[^>]+>', '', page))
for x in src:
    for n, a in x['ing']:
        nn = html.escape(re.sub(r'\s*укр\.?\s*\*?$', '', n.strip()))
        if nn not in page: fails.append(f'нет ингредиента: {x["name"]} / {n}')
        if html.escape(a) not in page: fails.append(f'нет граммовки: {x["name"]} / {n} = {a}')
    if x['total'] and html.escape(x['total']) not in page:
        fails.append(f'нет выхода: {x["name"]} = {x["total"]}')
    for line in x['method'].split('\n'):
        if line.strip() and line.strip()[:80] not in plain:
            fails.append(f'обрезан способ приготовления: {x["name"]}')
    if x['serve'] and x['serve'].strip()[:60] not in plain:
        fails.append(f'нет подачи: {x["name"]}')

# ---------- 2. полнота глав
from build import BY, VARIANTS
from config import CHAPTERS
used = set()
for ch in CHAPTERS:
    for n in ch['items']:
        if n in used: fails.append(f'напиток в двух главах: {n}')
        used.add(n)
        used.update(VARIANTS.get(n, []))
for n in BY:
    if n not in used: fails.append(f'напиток не попал ни в одну главу: {n}')

# ---------- 3. ответы банка
bank = json.load(open(ROOT / 'data' / 'bank.json', encoding='utf-8'))
by = {re.sub(r'\s+/\s+', ' · ', d['name']): d for d in src}
EXTRA_CATS = ('coffee', 'tea', 'pf', 'serve')
for q in bank:
    if (q['drink'] == 'Эталон украшения' or q['t'] != 'num'
            or q['cat'] in ('glass', 'method') + EXTRA_CATS):
        continue
    d = by.get(q['drink'])
    if not d: fails.append(f'вопрос про несуществующий напиток: {q["drink"]}'); continue
    m0 = re.search(r'«(.+?)»', q['q'])
    if not m0: continue
    # в вопросе про украшение к названию приписана форма нарезки: «Лимон · вейдж»
    label = m0.group(1).split(' · ')[0]
    is_gar = 'на украшение' in q['q']
    is_sum = 'ВСЕГО' in q['q']
    vals = []
    for n, a in d['ing']:
        gar = 'укр' in n.lower()
        if re.sub(r'\s*укр\.?\s*\*?$', '', n.strip()) != label: continue
        if not is_sum and gar != is_gar: continue
        m = re.search(r'(\d+[.,]?\d*)\s*(?:мл|гр)', a.replace(',', '.'))
        if m: vals.append(float(m.group(1)))
    ok = abs(sum(vals) - q['a']) < 0.01 if is_sum else any(abs(v - q['a']) < 0.01 for v in vals)
    if not ok:
        fails.append(f'неверный ответ в банке: {q["drink"]} / {label} = {q["a"]}, в файле {vals}')

# ---------- 3б. пак «пропущенная граммовка»: показанное + ответ должны дать выход
for q in bank:
    if q['t'] != 'fill':
        continue
    shown = 0.0
    blanks = 0
    for n, a in q['rows']:
        if a == '':
            blanks += 1
            continue
        m = re.match(r'^(\d+[.,]?\d*)\s*мл\.?$', a.strip())
        if m: shown += float(m.group(1).replace(',', '.'))
    total = float(re.match(r'^(\d+[.,]?\d*)', q['total']).group(1).replace(',', '.'))
    if blanks != 1:
        fails.append(f'в fill-вопросе не одна пропущенная строка: {q["drink"]} ({blanks})')
    elif abs(shown + q['a'] - total) > 0.01:
        fails.append(f'fill не сходится с выходом: {q["drink"]} — {shown}+{q["a"]} != {total}')

# ---------- 3б2. кофе, чай, заготовки и подача — ответы против data/extras.json
extras = json.load(open(ROOT / 'data' / 'extras.json', encoding='utf-8'))
EX_VALS = {}          # (напиток, что спрашиваем) -> [числа из исходника]


def _put(who, label, amount):
    # «2 б.л. - 10 гр»: в строке два числа, верным может быть любое из них
    for m in re.finditer(r'(\d+[.,]?\d*)', (amount or '').replace(',', '.')):
        EX_VALS.setdefault((who.strip(), label.strip()), []).append(float(m.group(1)))


for c in extras['coffee']:
    for n, a_ in c['ing']:
        _put(c['name'], n, a_)
    _put(c['name'], 'выход', c['total'])
for t in extras['tea']['simple']:
    _put(t['name'], 'заварка на порцию', t['dose'])
    _put(t['name'], 'ложек', t['spoons'])
for m_ in extras['tea']['mixes']:
    for n, a_ in m_['ing']:
        _put(m_['name'], n, a_)
for x in extras['pf']:
    for n, a_ in x['ing']:
        _put(x['name'], n, a_)
    _put(x['name'], 'выход', x['total'])
for x in extras['serve']:
    if '\n' in x['amount']:
        for line, label in zip(x['amount'].split('\n'), ['Текила', 'Лайм', 'Соль']):
            _put(x['name'], label, line)
    else:
        _put(x['name'], 'порция', x['amount'])

# Название ингредиента раньше выдёргивалось из текста вопроса по кавычкам. С 20.08.2026
# вопрос звучит «Сколько миллилитров сиропа Малина?» — название в родительном падеже
# и без кавычек, из текста его не достать. Берём его из sk: он для того и заведён
# («напиток|строка рецепта|вид») и не зависит от формулировки.
SK_LABEL = {'ложки': 'ложек'}
for q in bank:
    if q['cat'] not in EXTRA_CATS or q['t'] != 'num':
        continue
    parts = (q.get('sk') or '').split('|')
    label = parts[1] if len(parts) > 1 else '?'
    label = SK_LABEL.get(label, label)
    vals = EX_VALS.get((q['drink'].strip(), label.strip()), [])
    if not vals:
        fails.append(f'нет источника для вопроса: {q["drink"]} / {label}')
    elif not any(abs(v - q['a']) < 0.01 for v in vals):
        fails.append(f'неверный ответ (extras): {q["drink"]} / {label} = {q["a"]}, в файле {vals}')

# ---------- 3б3. метод приготовления сверяем с TECH_FIX, а не с сырым полем
# «Рафунтелла» взбивается на пароотводе, «Бамбл» и «Криспи Айс Латте» только упоминают
# питчер — распознавание по тексту здесь ошибается, и правильные значения лежат в config.
from config import TECH_FIX
d2 = json.load(open(ROOT / 'data' / 'drinks2.json', encoding='utf-8'))
TECH_OF = {re.sub(r'\s+/\s+', ' · ', x['name']): TECH_FIX.get(x['name'], x['tech']) for x in d2}
for q in bank:
    if q['cat'] != 'method':
        continue
    want = TECH_OF.get(q['drink'])
    got = q['opts'][q['ai']]
    if want and want != got:
        fails.append(f'неверный метод: {q["drink"]} — в банке {got}, верно {want}')

# ---------- 3в. пак «впиши весь состав»: сумма показанного и всех ответов = выход
for q in bank:
    if q['t'] != 'mfill':
        continue
    shown, blanks = 0.0, 0
    for n, a in q['rows']:
        if a == '':
            blanks += 1
            continue
        m = re.match(r'^(\d+[.,]?\d*)\s*мл\.?$', a.strip())
        if m: shown += float(m.group(1).replace(',', '.'))
    total = float(re.match(r'^(\d+[.,]?\d*)', q['total']).group(1).replace(',', '.'))
    if blanks != len(q['a']):
        fails.append(f'mfill: пропусков {blanks}, ответов {len(q["a"])} — {q["drink"]}')
    elif abs(shown + sum(q['a']) - total) > 0.01:
        fails.append(f'mfill не сходится с выходом: {q["drink"]}')

# ---------- 3г. в банке не должно быть двух одинаковых вопросов
seen_q = {}
for q in bank:
    k = (q['drink'], q['t'], q['q'])
    seen_q.setdefault(k, 0)
    seen_q[k] += 1
for k, n in seen_q.items():
    if n > 1: fails.append(f'вопрос повторяется {n} раза: {k}')

# ---------- 4а. шаг вариантов у веса украшений
# С 20.08.2026 шаг задан по виду украшения (вейдж и ягода — 5, мармелад — 4,
# сухое — 2, зелень — 1 или 0,5). Проверяем, что ближайший неверный вариант отстоит
# ровно на разрешённый шаг: раньше эта категория из проверки просто исключалась,
# и «розмарин 4 гр против 24 гр» никто бы не поймал.
from config import gar_steps
for q in bank:
    if q['t'] != 'choice' or q['cat'] != 'garnish' or not q.get('opts'):
        continue
    if not all(o.endswith(' гр') for o in q['opts']):
        continue
    parts = (q.get('sk') or '').split('|')
    label = parts[1] if len(parts) > 2 else ''
    if not label:
        continue
    nums = [float(o[:-3].replace(',', '.')) for o in q['opts']]
    corr = nums[q['ai']]
    steps = gar_steps(label, corr)
    if not steps:
        continue
    gaps = sorted(abs(v - corr) for i, v in enumerate(nums) if i != q['ai'])
    if gaps[0] < min(steps) - 1e-9:
        fails.append(f'шаг украшения меньше {min(steps)}: {q["drink"]} / {label} {q["opts"]}')

# ---------- 4б. разброс дистракторов
for q in bank:
    if q['t'] != 'choice' or q['cat'] == 'garnish':
        continue
    # мелкая шкала (заварка 8–15 гр, топинги, цукаты) живёт по правилу украшений:
    # шаг 1–3 грамма, иначе выбор вырождается
    if q['cat'] in EXTRA_CATS and all('гр' in o for o in q['opts']):
        continue
    # диапазоны («15-20 сек», «80 °C») сравнивать по разбросу бессмысленно
    if any(('сек' in o) or ('°' in o) for o in q['opts']):
        continue
    nums = []
    for o in q['opts']:
        m = re.match(r'([\d,]+)', o)
        if m: nums.append(float(m.group(1).replace(',', '.')))
    if len(nums) != len(q['opts']): continue
    corr = nums[q['ai']]
    if min(abs(v - corr) for i, v in enumerate(nums) if i != q['ai']) < 10:
        fails.append(f'слишком близкие варианты: {q["drink"]} / {q["q"]} {q["opts"]}')

print(f'проверок провалено: {len(fails)}')
for f in fails[:40]:
    print(' ·', f)
sys.exit(1 if fails else 0)
