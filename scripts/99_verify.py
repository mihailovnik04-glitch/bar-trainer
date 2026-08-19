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
for q in bank:
    if q['drink'] == 'Эталон украшения' or q['cat'] == 'glass' or q['t'] != 'num':
        continue
    d = by.get(q['drink'])
    if not d: fails.append(f'вопрос про несуществующий напиток: {q["drink"]}'); continue
    label = re.search(r'«(.+?)»', q['q']).group(1)
    vals = []
    for n, a in d['ing']:
        if re.sub(r'\s*укр\.?\s*\*?$', '', n.strip()) == label:
            m = re.search(r'(\d+[.,]?\d*)\s*(?:мл|гр)', a.replace(',', '.'))
            if m: vals.append(float(m.group(1)))
    if not any(abs(v - q['a']) < 0.01 for v in vals):
        fails.append(f'неверный ответ в банке: {q["drink"]} / {label} = {q["a"]}, в файле {vals}')

# ---------- 4. разброс дистракторов
for q in bank:
    if q['t'] != 'choice' or q['cat'] == 'garnish':
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
