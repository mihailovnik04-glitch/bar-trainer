# -*- coding: utf-8 -*-
"""Генерация банка вопросов для теста по барному пособию."""
import json, re, os, base64, random
from PIL import Image

from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
W = str(ROOT)
drinks = json.load(open(f'{W}/data/drinks2.json', encoding='utf-8'))
cells = json.load(open(f'{W}/data/data.json', encoding='utf-8'))
imgs = json.load(open(f'{W}/data/images.json', encoding='utf-8'))

SIMPLE = re.compile(r'^(\d+[.,]?\d*)\s*(мл|гр)\.?$')
WITHGR = re.compile(r'(\d+[.,]?\d*)\s*гр')

def parse_amount(a):
    """-> (value, unit, hint) либо None"""
    a = (a or '').strip()
    if not a: return None
    m = SIMPLE.match(a)
    if m:
        return float(m.group(1).replace(',', '.')), m.group(2), ''
    if 'прогон' in a or 'часть' in a or '/' in a and 'кольцо' not in a:
        return None
    m = WITHGR.search(a)
    if m:
        pre = a[:m.start()].strip(' -–')
        return float(m.group(1).replace(',', '.')), 'гр', (f'указано как «{a}»' if pre else '')
    return None

def fmtnum(v):
    return str(int(v)) if float(v).is_integer() else str(v).replace('.', ',')

def clean_gar(n):
    return re.sub(r'\s*укр\.?\s*\*?$', '', n.strip())

def pretty(name):
    return re.sub(r'\s+/\s+', ' · ', name)

# ------------------------------------------------- картинки
# Раньше data-URI подставлялся в КАЖДЫЙ вопрос — одна и та же картинка копировалась
# по 8 раз и bank.js весил 3,8 МБ. Теперь вопрос хранит ключ ("image41"),
# а сами картинки лежат один раз в data/media.json -> window.IMG.
os.makedirs(f'{W}/thumb', exist_ok=True)
MEDIA = {}
THUMB_PX = 460          # хватает и для кружка 52 px, и для фото в карточке рецепта

def thumb(path):
    """media/image41.png -> 'image41' (ключ в MEDIA)"""
    if not path: return ''
    base = os.path.splitext(os.path.basename(path))[0]
    if base in MEDIA: return base
    src = f'{W}/img/{base}.jpg'
    if not os.path.exists(src): return ''
    im = Image.open(src)
    w, h = im.size
    s = THUMB_PX / max(w, h)
    if s < 1: im = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out = f'{W}/thumb/{base}.jpg'
    im.convert('RGB').save(out, 'JPEG', quality=70, optimize=True)
    MEDIA[base] = 'data:image/jpeg;base64,' + base64.b64encode(open(out, 'rb').read()).decode()
    return base

# ------------------------------------------------- банк
bank = []
def add(**kw):
    kw['id'] = f'q{len(bank)}'
    bank.append(kw)

def steps_for(v):
    if v <= 20: return [10, 15, 20]
    if v <= 60: return [10, 15, 20, 30]
    return [20, 25, 30, 40]

def distractors(v, unit, rnd):
    """3 неверных варианта: отклонение 10–40 в зависимости от масштаба"""
    out = []
    tries = 0
    while len(out) < 3 and tries < 300:
        tries += 1
        d = rnd.choice(steps_for(v)) * rnd.choice([-1, 1])
        cand = v + d
        if cand <= 0: continue
        if v >= 100: cand = round(cand / 5) * 5
        if cand == v or cand in out: continue
        if abs(cand - v) < 10: continue
        out.append(cand)
    return out

rnd = random.Random(7)
GLASS_SKIP = {'', 'Шоты', 'Шоты (4 шт)', 'Стакан с собой', 'Бутылка ПЭТ', 'Ступенька М', 'Кувшин 1 л'}
GLASS_NORM = {'Олд фешн': 'Олд Фешн', 'Банка c ручкой': 'Банка с ручкой',
              'Хайбол 620 / Ступенька XL': 'Хайбол 620 (Ступенька XL)'}
GLASS_RARE = {'Айриш', 'Сова', 'Череп', 'Шейкер', 'Стэмлесс', 'Слинг', 'Жестяная банка',
              'Ступенька XL', 'Ступенька L', 'Хайбол 620 (Ступенька XL)', 'Олд Фешн',
              'Джин Тоник', 'Цветная чашка', 'Банка с ручкой'}

for d in drinks:
    if 'Безо льда' in d['name']:
        continue
    nm = pretty(d['name'])
    im = thumb(d['photos'][0] if d['photos'] else '')
    seen = {}
    for n, a in d['ing']:
        seen[n] = seen.get(n, 0) + 1
    # --- граммовки компонентов и украшений
    for n, a in d['ing']:
        if seen[n] > 1:      # неоднозначные повторы (напр. водка в двух парах шотов)
            continue
        p = parse_amount(a)
        if not p: continue
        v, unit, hint = p
        is_gar = 'укр' in n.lower()
        label = clean_gar(n)
        cat = 'garnish' if is_gar else 'grams'
        q = (f'Сколько «{label}» идёт в украшение?' if is_gar
             else f'Сколько «{label}»?')
        # 85% — ввод точного значения, 15% — выбор
        if rnd.random() < 0.15:
            opts = distractors(v, unit, rnd) + [v]
            rnd.shuffle(opts)
            add(t='choice', cat=cat, drink=nm, q=q, hint=hint, img=im,
                opts=[f'{fmtnum(o)} {unit}' for o in opts],
                ai=opts.index(v))
        else:
            add(t='num', cat=cat, drink=nm, q=q, hint=hint, img=im, unit=unit, a=v)
    # --- посуда (немного, только характерная)
    gl = GLASS_NORM.get(d['glass'], d['glass'])
    if gl not in GLASS_SKIP and gl in GLASS_RARE:
        add(t='glass', cat='glass', drink=nm, q='В какой посуде подаётся напиток?', img=im, ans=gl)
    # --- чем украшается
    gars = [clean_gar(n) for n, a in d['ing'] if 'укр' in n.lower()]
    if len(gars) >= 2:
        add(t='garset', cat='garnish', drink=nm, q='Чем украшается напиток?', img=im,
            ans=' + '.join(gars))

# ------------------------------------------------- эталонные веса украшений
G = {}
for row in cells['Украшения']:
    r = row[0]
    G[r] = {i + 1: v for i, v in enumerate(row[1:]) if v.strip()}
rows_ = [1, 17, 33, 51, 67, 83]
pics = imgs.get('Украшения', [])
for bi, r0 in enumerate(rows_):
    r1 = rows_[bi + 1] - 1 if bi + 1 < len(rows_) else 98
    for col in (1, 3, 5, 7):
        label = G.get(r0, {}).get(col, '').strip()
        weight = G.get(r0 + 1, {}).get(col + 1, '').strip()
        if not label or not weight: continue
        label = re.sub(r'\s*\(на фото[^)]*\)', '', label)
        p = parse_amount(re.sub(r'^\d+\s*шт\s*-\s*', '', re.sub(r'\s+', ' ', weight)))
        if not p: continue
        v, unit, _ = p
        cand = sorted([i for i in pics if r0 <= i['row'] <= r1 and i['col'] == col], key=lambda i: i['row'])
        add(t='num', cat='garnish', drink='Эталон украшения', q=f'Сколько весит: {label}?',
            hint='', img=thumb(cand[0]['file'] if cand else ''), unit=unit, a=v)

# ------------------------------------------------- варианты для посуды
glasses = sorted({q['ans'] for q in bank if q['t'] == 'glass'})
for q in bank:
    if q['t'] == 'glass':
        others = [g for g in glasses if g != q['ans']]
        rnd.shuffle(others)
        opts = others[:3] + [q['ans']]
        rnd.shuffle(opts)
        q['opts'] = opts
        q['ai'] = opts.index(q['ans'])
        q.pop('ans')
    elif q['t'] == 'garset':
        pool = [x['ans'] for x in bank if x['t'] == 'garset' and x['ans'] != q['ans']]
        rnd.shuffle(pool)
        opts = pool[:3] + [q['ans']]
        rnd.shuffle(opts)
        q['opts'] = opts
        q['ai'] = opts.index(q['ans'])
        q.pop('ans')
        q['t'] = 'choice'

# ------------------------------------------------- справочник для приложения
import sys
sys.path.insert(0, f'{W}/scripts')
from config import CHAPTERS, MNEMO, FAMILY_NOTE, TECH_FIX

CH_OF, CH_LIST = {}, []
for ch in CHAPTERS:
    CH_LIST.append({'id': ch['id'], 'title': ch['title'], 'color': ch['color'], 'sub': ch['sub']})
    for nm in ch['items']:
        CH_OF[nm] = ch['id']

BYNAME = {d['name']: d for d in drinks}
VARIANTS = {}
for d in drinks:
    if 'Безо льда' in d['name']:
        VARIANTS.setdefault(d['name'].split(' / Безо льда')[0], []).append(d['name'])

recipes, R_INDEX = [], {}
for ch in CHAPTERS:
    for nm in ch['items']:
        d = BYNAME[nm]
        R_INDEX[pretty(nm)] = len(recipes)
        recipes.append({
            'name': pretty(nm), 'ch': ch['id'],
            'tech': TECH_FIX.get(nm, d['tech']), 'glass': GLASS_NORM.get(d['glass'], d['glass']),
            'straw': d['straw'], 'total': d['total'],
            'ing': [[n, a] for n, a in d['ing_main']],
            'gar': [[clean_gar(n), a] for n, a in d['garnish']],
            'method': d['method'], 'serve': d['serve'],
            'formula': ' + '.join(f'{v} {n}' for v, n in d['formula']),
            'key': MNEMO.get(nm) or FAMILY_NOTE.get(nm, ''),
            'img': thumb(d['photos'][0] if d['photos'] else ''),
            'var': [{'name': pretty(v), 'method': BYNAME[v]['method']} for v in VARIANTS.get(nm, [])],
        })

for q in bank:                       # связываем вопрос с карточкой рецепта
    if q['drink'] in R_INDEX:
        q['r'] = R_INDEX[q['drink']]

# Стабильный id: позиция в массиве меняется при любой перегенерации банка, и тогда
# сохранённые ошибки «съезжали» на чужие вопросы. Хеш от напитка и текста вопроса
# переживает пересборку; меняется только если сам вопрос переформулирован.
import hashlib
seen = {}
for q in bank:
    q['id'] = hashlib.sha1(f"{q['drink']}|{q['cat']}|{q['q']}".encode()).hexdigest()[:10]
    seen.setdefault(q['id'], []).append(q['q'])
dupes = {k: v for k, v in seen.items() if len(v) > 1}
if dupes:
    raise SystemExit(f'Коллизия id вопросов: {dupes}')

json.dump({'chapters': CH_LIST, 'recipes': recipes},
          open(f'{W}/data/recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(MEDIA, open(f'{W}/data/media.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(bank, open(f'{W}/data/bank.json', 'w', encoding='utf-8'), ensure_ascii=False)
from collections import Counter
print('вопросов:', len(bank), Counter((q['cat'], q['t']) for q in bank))
print('рецептов:', len(recipes), '· картинок:', len(MEDIA))
print('посуда:', glasses)
