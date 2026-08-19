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
extras = json.load(open(f'{W}/data/extras.json', encoding='utf-8'))

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

# ------------------------------------------------- формы нарезки украшений
# Лист «Украшения» — это эталон «продукт + форма = вес» (Апельсин вейдж 30, кольцо 25,
# полкольца 12,5 …). В рецептах форма не написана, есть только вес, поэтому форму
# восстанавливаем по весу. Ничего не досочиняем: если вес не совпал с эталоном
# и не кратен ему — форму не пишем.
GAR_FORMS = {}          # (продукт, вес) -> форма

def _load_forms():
    rows = {r[0]: r[1:] for r in cells['Украшения']}
    for r0 in (1, 17, 33, 51, 67, 83):
        head, wline = rows.get(r0), rows.get(r0 + 1)
        if not head or not wline:
            continue
        for col in (1, 3, 5, 7):
            lab = re.sub(r'\s*\(на фото[^)]*\)', '', head[col - 1]).strip()
            m = re.search(r'(\d+[.,]?\d*)\s*гр', wline[col])
            if not lab or ' - ' not in lab or not m:
                continue
            prod, _, form = lab.partition(' - ')
            GAR_FORMS[(prod.strip().lower(), float(m.group(1).replace(',', '.')))] = form.strip()

_load_forms()
PLURAL = {'вейдж': 'вейджа', 'кольцо': 'кольца', 'полкольца': 'полукольца'}

def gar_form(name, amount):
    """'Лимон', '50 гр' -> '2 вейджа'. Пусто, если форму не восстановить однозначно."""
    m = re.search(r'(\d+[.,]?\d*)\s*гр', (amount or '').replace(',', '.'))
    if not m:
        return ''
    v, prod = float(m.group(1)), name.strip().lower()
    if (prod, v) in GAR_FORMS:                       # вес совпал с эталоном
        return GAR_FORMS[(prod, v)]
    # кратные порции: «2 вейджа», «3 кольца». Только цитрусовая лестница — у веточек
    # и соцветий кратность из веса не выводится.
    best = None
    for (p, base), form in GAR_FORMS.items():
        if p != prod or form not in PLURAL or base <= 0:
            continue
        k = v / base
        if abs(k - round(k)) < 1e-9 and 2 <= round(k) <= 4:
            k = round(k)
            if best is None or k < best[0]:
                best = (k, form)
    return f'{best[0]} {PLURAL[best[1]]}' if best else ''

def gar_label(name, amount):
    """Название украшения с формой нарезки: 'Лимон · вейдж'."""
    base = clean_gar(name)
    f = gar_form(base, amount)
    return f'{base} · {f}' if f else base

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

def distractors(v, unit, rnd, fine=False):
    """3 неверных варианта. Обычно отклонение 10–40, а для веса украшений (fine)
    шаг 1–3 грамма: розмарин 4 гр против варианта 24 гр — не вопрос, а подарок."""
    out = []
    tries = 0
    steps = [1, 2, 3] if fine else None
    while len(out) < 3 and tries < 400:
        tries += 1
        d = rnd.choice(steps or steps_for(v)) * rnd.choice([-1, 1])
        cand = round(v + d, 1)
        if cand <= 0: continue
        if not fine and v >= 100: cand = round(cand / 5) * 5
        if cand == v or cand in out: continue
        if not fine and abs(cand - v) < 10: continue
        out.append(cand)
    k = 0
    while len(out) < 3:                  # веса 1–2 гр не дают трёх вариантов вниз
        k += 1
        cand = round(v + k, 1)
        if cand not in out and cand != v: out.append(cand)
    return out

rnd = random.Random(7)
GLASS_SKIP = {'', 'Шоты', 'Шоты (4 шт)', 'Стакан с собой', 'Бутылка ПЭТ', 'Ступенька М', 'Кувшин 1 л'}
# «Хайбол 620», «Ступенька XL» и «Стакан XL» — одна и та же посуда, в исходнике
# записана тремя способами. Сводим к одному варианту, иначе у вопроса про посуду
# оказывается два правильных ответа сразу.
XL = 'Хайбол 620 (Стакан XL)'
GLASS_NORM = {'Олд фешн': 'Олд Фешн', 'Банка c ручкой': 'Банка с ручкой',
              'Хайбол 620 / Ступенька XL': XL, 'Ступенька XL': XL, 'Стакан XL': XL}
GLASS_RARE = {'Айриш', 'Сова', 'Череп', 'Шейкер', 'Стэмлесс', 'Слинг', 'Жестяная банка',
              'Ступенька L', XL, 'Олд Фешн',
              'Джин Тоник', 'Цветная чашка', 'Банка с ручкой'}

# ------------------------------------------------- вид отдачи
# «Клубничный лимонад 1 л» и «Клубничный лимонад» — разные напитки с разными граммовками.
# Без пометки вопрос неотличим, поэтому вид отдачи пишем всегда, где он есть.
ICED = {d['name'].split(' / Безо льда')[0] for d in drinks if 'Безо льда' in d['name']}

# Семья напитка: «Лимонделло», «Лимонделло / Кувшин», «Лимонделло 0.5 л» и «… / с собой» —
# один напиток в разных объёмах и подачах, но с разными граммовками. Там, где версий
# больше одной, объём обязателен в пометке — иначе вопрос неотличим от соседнего.
def family(name):
    n = name.lower().replace('ё', 'е')
    n = re.sub(r'\s*/\s*(кувшин|безо льда|с собой|с ежевикой)', '', n)
    n = re.sub(r'\s*\d+[.,]?\d*\s*л\b', '', n)
    n = re.sub(r'\s*б/а|\s*0,0', '', n)
    return n.strip()

FAMILY_N = {}
for d in drinks:
    FAMILY_N[family(d['name'])] = FAMILY_N.get(family(d['name']), 0) + 1

def tag_of(d):
    nm = d['name']
    parts = []
    if d['sheet'] == 'Самовывоз':
        parts = ['на самовывоз', 'бутылка ПЭТ']
    elif 'с собой' in nm.lower():
        parts = ['с собой']
    else:
        if 'Кувшин' in nm: parts.append('кувшин 1 л')
        if 'Безо льда' in nm: parts.append('безо льда')
        elif nm in ICED: parts.append('со льдом')  # есть парный вариант безо льда
    # «С собой» и «Самовывоз» — версии по определению, даже если в таблице их назвали
    # иначе («Щавель-горох» против «Щавель-Зеленый горошек»): объём пишем всегда.
    multi = (FAMILY_N.get(family(nm), 0) > 1
             or d['sheet'] in ('Лимонады с собой (Акция)', 'Самовывоз')
             or 'Кувшин' in nm)
    if multi and d['total']:
        parts.append(d['total'])
    return ' · '.join(parts)

for d in drinks:
    if 'Безо льда' in d['name']:
        continue
    nm = pretty(d['name'])
    tg = tag_of(d)
    sh = d['sheet']
    im = thumb(d['photos'][0] if d['photos'] else '')
    seen = {}
    for n, a in d['ing']:
        seen[n] = seen.get(n, 0) + 1
    # Один и тот же продукт может идти и в состав, и на украшение — с разными весами
    # (розмарин во взваре: 3 гр внутрь, 4 гр сверху). Суммировать их нельзя, поэтому
    # такие строки спрашиваем раздельно и обязательно уточняем, о чём речь.
    both = {clean_gar(n).lower() for n, _ in d['ing'] if 'укр' in n.lower()} &            {n.strip().lower() for n, _ in d['ing'] if 'укр' not in n.lower()}

    def ask(n, a, is_gar):
        p = parse_amount(a)
        if not p: return
        v, unit, hint = p
        label = clean_gar(n)
        dual = label.lower() in both
        if is_gar:
            cat = 'garnish'
            title = gar_label(n, a)
            q = (f'Сколько «{title}» идёт ТОЛЬКО на украшение?' if dual
                 else f'Сколько «{title}» идёт на украшение?')
            hint = ''            # «указано как 4 шт - 8 гр» просили убрать
        else:
            cat = 'grams'
            q = (f'Сколько «{label}» идёт в состав, не считая украшения?' if dual
                 else f'Сколько «{label}»?')
        kw = dict(cat=cat, drink=nm, tag=tg, sh=sh, q=q, hint=hint, img=im,
                  sk=f'{nm}|{label}|{"g" if is_gar else "i"}')
        # 60% — ввод точного значения, 40% — выбор из четырёх (заказчик просил больше выбора)
        if rnd.random() < 0.40:
            opts = distractors(v, unit, rnd, fine=(is_gar and unit == 'гр' and v <= 30)) + [v]
            rnd.shuffle(opts)
            add(t='choice', opts=[f'{fmtnum(o)} {unit}' for o in opts], ai=opts.index(v), **kw)
        else:
            add(t='num', unit=unit, a=v, **kw)

    for n, a in d['ing']:
        if seen[n] > 1:      # неоднозначные повторы (напр. водка в двух парах шотов)
            continue
        ask(n, a, 'укр' in n.lower())

    # --- суммарный вес продукта, который идёт и внутрь, и на украшение
    for prod in sorted(both):
        vals = []
        for n, a in d['ing']:
            if clean_gar(n).lower() != prod: continue
            p = parse_amount(a)
            if p: vals.append(p)
        if len(vals) != 2 or vals[0][1] != vals[1][1]: continue
        total_v, unit = vals[0][0] + vals[1][0], vals[0][1]
        label = next(clean_gar(n) for n, _ in d['ing'] if clean_gar(n).lower() == prod)
        add(t='num', cat='grams', drink=nm, tag=tg, sh=sh, img=im, unit=unit, a=total_v,
            q=f'Сколько «{label}» уходит на напиток ВСЕГО — и в состав, и на украшение?',
            hint='', sk=f'{nm}|{label}|sum')

    # --- посуда (немного, только характерная). Картинку не показываем:
    # по фото бокал угадывается без знания рецептуры.
    gl = GLASS_NORM.get(d['glass'], d['glass'])
    if gl not in GLASS_SKIP and gl in GLASS_RARE:
        add(t='glass', cat='glass', drink=nm, tag=tg, sh=sh, img='',
            q='В какой посуде подаётся напиток?', ans=gl, sk=f'{nm}|glass')
    # --- чем украшается
    gars = [gar_label(n, a) for n, a in d['ing'] if 'укр' in n.lower()]
    if len(gars) >= 2:
        add(t='garset', cat='garnish', drink=nm, tag=tg, sh=sh, img=im,
            q='Чем украшается напиток?', ans=' + '.join(gars), sk=f'{nm}|garset')

# ------------------------------------------------- количество и форма украшений
# Штучные украшения (бамбуковый лист, зонтик, сахарная картинка, мармеладное желе)
# в исходнике записаны без граммов — «1 шт», «2 шт», — поэтому в вопросы про вес они
# не попадали вовсе. Спрашиваем их отдельно: сколько штук и в какой форме.
PIECE = re.compile(r'^(\d+)\s*шт\.?$')
PIECE_IN = re.compile(r'^(\d+)\s*шт')

def piece_count(a):
    """'2 шт' -> '2 шт'; '4 шт - 32 гр' -> '4 шт'. Иначе пусто."""
    a = (a or '').strip()
    m = PIECE_IN.match(a)
    return f'{m.group(1)} шт' if m else ''

# Варианты берём из реально встречающихся количеств, ничего не придумываем.
PIECE_POOL = set()
for d in drinks:
    for n, a in d['ing']:
        if 'укр' in n.lower():
            c = piece_count(a)
            if c: PIECE_POOL.add(c)
PIECE_POOL = sorted(PIECE_POOL, key=lambda x: int(x.split()[0]))

piece_n = 0
for d in drinks:
    if 'Безо льда' in d['name']:
        continue
    nm, tg, sh = pretty(d['name']), tag_of(d), d['sheet']
    im = thumb(d['photos'][0] if d['photos'] else '')
    seen_g = {}
    for n, a in d['ing']:
        seen_g[n] = seen_g.get(n, 0) + 1
    for n, a in d['ing']:
        if 'укр' not in n.lower() or seen_g[n] > 1:
            continue
        cnt = piece_count(a)
        if not cnt:
            continue
        label = clean_gar(n)
        # Заказчик: из чисто штучного спрашиваем только бамбуковый лист. Зонтик,
        # наклейка, пергамент и сахарные картинки — не рецептура, а сборка подачи.
        if 'гр' not in a and 'бамбук' not in label.lower():
            continue
        others = [c for c in PIECE_POOL if c != cnt]
        rnd.shuffle(others)
        opts = others[:3] + [cnt]
        if len(opts) < 4:
            continue
        rnd.shuffle(opts)
        add(t='choice', cat='garnish', drink=nm, tag=tg, sh=sh, img=im, hint='',
            q=f'Сколько штук «{label}» идёт на украшение?',
            opts=opts, ai=opts.index(cnt), sk=f'{nm}|{label}|pcs')
        piece_n += 1

# Форма нарезки с листа «Украшения»: целый лист или две половинки, вейдж или кольцо.
# Варианты — тоже только реальные формы из того же листа.
FORM_POOL = sorted({f for f in GAR_FORMS.values()})
form_n = 0
for (prod, weight), form in sorted(GAR_FORMS.items()):
    others = [f for f in FORM_POOL if f != form]
    if len(others) < 3:
        continue
    rnd.shuffle(others)
    opts = others[:3] + [form]
    rnd.shuffle(opts)
    title = prod[:1].upper() + prod[1:]
    add(t='choice', cat='garnish', drink='Эталон украшения', tag='эталон', sh='Украшения',
        img='', hint='', q=f'В какой форме режется «{title}» на {fmtnum(weight)} гр?',
        opts=opts, ai=opts.index(form), sk=f'эталон|{prod}|{fmtnum(weight)}|form')
    form_n += 1

# ------------------------------------------------- паки на состав целиком
# Показываем состав, часть строк прячем — их нужно вписать. Вопрос честный только там,
# где выход равен сумме жидкостей: тогда пропуск действительно вычисляется, а не угадывается.
ML = re.compile(r'^(\d+[.,]?\d*)\s*мл\.?$')

def ml(a):
    m = ML.match((a or '').strip())
    return float(m.group(1).replace(',', '.')) if m else None

fill_n = mfill_n = 0
for d in drinks:
    if 'Безо льда' in d['name']:
        continue
    out = ml(d['total'])
    if not out:
        continue
    rows = [(n, a, ml(a)) for n, a in d['ing'] if 'укр' not in n.lower()]
    liq = [r for r in rows if r[2] is not None]
    if len(liq) < 3 or len({n for n, _, _ in rows}) != len(rows):
        continue                                  # мало строк или повторы названий
    if abs(sum(r[2] for r in liq) - out) > 0.01:
        continue                                  # выход не сходится — пропуск не вычислить
    nm, tg, sh = pretty(d['name']), tag_of(d), d['sheet']
    im = thumb(d['photos'][0] if d['photos'] else '')

    # 1. одна стёртая строка. Раньше брали одну случайную на напиток — теперь до трёх разных,
    # каждая со своим id: банк растёт, а вопросы остаются разными.
    for hide in rnd.sample(liq, min(3, len(liq))):
        add(t='fill', cat='grams', drink=nm, tag=tg, sh=sh,
            q=f'Одна граммовка стёрлась. Сколько «{hide[0]}»?',
            unit='мл', a=hide[2], total=d['total'],
            rows=[[n, ('' if (n, a) == (hide[0], hide[1]) else a)] for n, a, _ in rows],
            img=im, hint='выход = сумма всех жидкостей',
            sk=f'{nm}|{hide[0]}|fill')
        fill_n += 1

    # 2. вписать несколько граммовок сразу: 3–4 строки или весь состав.
    #    Ответ — список чисел в порядке строк, проверяется каждое поле отдельно.
    packs = []
    if len(liq) >= 4:
        packs.append(('part', rnd.sample(liq, min(4, len(liq)))))
    packs.append(('all', liq))
    for kind, chosen in packs:
        hidden = {(r[0], r[1]) for r in chosen}
        order = [r for r in rows if (r[0], r[1]) in hidden]
        add(t='mfill', cat='grams', drink=nm, tag=tg, sh=sh,
            q=('Впишите все граммовки состава' if kind == 'all'
               else f'Впишите граммовки: {len(order)} строки'),
            unit='мл', total=d['total'],
            a=[r[2] for r in order],
            rows=[[n, ('' if (n, a) in hidden else a)] for n, a, _ in rows],
            img=im, hint='', sk=f'{nm}|{kind}|mfill')
        mfill_n += 1

# ------------------------------------------------- метод приготовления (редко)
# CLAUDE.md раньше запрещал такие вопросы; заказчик 20.08.2026 попросил добавить их,
# но именно редко — один вопрос на каждый пятый напиток.
TECHS = ['Билд', 'Шейк', 'Стир', 'Блендер', 'Питчер']
method_n = 0
for i, d in enumerate(drinks):
    if 'Безо льда' in d['name'] or i % 5:
        continue
    nm, tech = pretty(d['name']), d['tech']
    if tech not in TECHS:
        continue
    others = [t for t in TECHS if t != tech]
    rnd.shuffle(others)
    opts = others[:3] + [tech]
    rnd.shuffle(opts)
    add(t='choice', cat='method', drink=nm, tag=tag_of(d), sh=d['sheet'],
        q='Каким способом готовится напиток?', hint='',
        img=thumb(d['photos'][0] if d['photos'] else ''),
        opts=opts, ai=opts.index(tech), sk=f'{nm}|tech')
    method_n += 1

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
        im = thumb(cand[0]['file'] if cand else '')
        add(t='num', cat='garnish', drink='Эталон украшения', tag='эталон', sh='Украшения',
            q=f'Сколько весит: {label}?', hint='', img=im, unit=unit, a=v,
            sk=f'эталон|{label}|num')
        # Заказчик просил больше вопросов про вес ягод и украшений: тот же эталон
        # ещё раз в виде выбора, с шагом в 1–3 грамма.
        opts = distractors(v, unit, rnd, fine=True) + [v]
        rnd.shuffle(opts)
        add(t='choice', cat='garnish', drink='Эталон украшения', tag='эталон', sh='Украшения',
            q=f'Какой вес у: {label}?', hint='', img=im,
            opts=[f'{fmtnum(o)} {unit}' for o in opts], ai=opts.index(v),
            sk=f'эталон|{label}|choice')

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

# ------------------------------------------------- кофе, чай, заготовки, подача
# Листы «Кофе», «Чай », «ПФ» и «Спец. подачи» разбирает 03_extras.py. Вопросы по ним
# устроены так же, как по коктейлям: спрашиваем только измеримое — граммовки, дозы,
# температуру, время экстракции и кнопку пролива, — и только то, что написано в файле.
def ask_amount(cat, sheet, who, label, amount, im='', extra_sk=''):
    """Один вопрос про величину: ввод числа или выбор из четырёх."""
    p = parse_amount(amount)
    if not p:
        return 0
    v, unit, hint = p
    fine = unit == 'гр' and v <= 30
    kw = dict(cat=cat, drink=who, tag='', sh=sheet, img=im, hint=hint,
              sk=f'{who}|{label}|{extra_sk or cat}')
    if rnd.random() < 0.40:
        opts = distractors(v, unit, rnd, fine=fine) + [v]
        rnd.shuffle(opts)
        add(t='choice', q=f'Сколько «{label}»?',
            opts=[f'{fmtnum(o)} {unit}' for o in opts], ai=opts.index(v), **kw)
    else:
        add(t='num', q=f'Сколько «{label}»?', unit=unit, a=v, **kw)
    return 1

extra_n = 0

# --- кофе: состав, выход, кнопка пролива, время экстракции
BUTTONS = sorted({c['button'] for c in extras['coffee'] if c['button']})
EXTRACTS = sorted({c['extract'] for c in extras['coffee'] if c['extract']})
for c in extras['coffee']:
    nm = c['name']
    for n, a in c['ing']:
        extra_n += ask_amount('coffee', 'Кофе', nm, n, a)
    if c['total']:
        p = parse_amount(c['total'])
        if p:
            add(t='num', cat='coffee', drink=nm, tag='', sh='Кофе', img='', hint='',
                q='Какой выход у напитка?', unit=p[1], a=p[0], sk=f'{nm}|выход|coffee')
            extra_n += 1
    # «кнопка пролива с изображением одной большой чашки» — единственное место в пособии,
    # где вообще описано, что нажимать на кофемашине.
    if c['button'] and len(BUTTONS) >= 4:
        others = [x for x in BUTTONS if x != c['button']]
        rnd.shuffle(others)
        opts = others[:3] + [c['button']]
        rnd.shuffle(opts)
        add(t='choice', cat='coffee', drink=nm, tag='', sh='Кофе', img='', hint='',
            q='Какую кнопку пролива нажимать?', opts=opts, ai=opts.index(c['button']),
            sk=f'{nm}|кнопка|coffee')
        extra_n += 1
    if c['extract'] and len(EXTRACTS) >= 3:
        others = [x for x in EXTRACTS if x != c['extract']]
        rnd.shuffle(others)
        opts = others[:3] + [c['extract']]
        rnd.shuffle(opts)
        add(t='choice', cat='coffee', drink=nm, tag='', sh='Кофе', img='', hint='',
            q='Сколько длится экстракция?', opts=opts, ai=opts.index(c['extract']),
            sk=f'{nm}|экстракция|coffee')
        extra_n += 1

# --- чай: дозировка, температура, количество ложек, состав крафтовых смесей
TEMPS = sorted({t['temp'] for t in extras['tea']['simple'] if t['temp']})
for t in extras['tea']['simple']:
    nm = t['name'].strip()
    extra_n += ask_amount('tea', 'Чай', nm, 'заварка на порцию', t['dose'])
    if t['temp'] and len(TEMPS) >= 2:
        others = [x for x in TEMPS if x != t['temp']]
        opts = others[:3] + [t['temp']]
        rnd.shuffle(opts)
        add(t='choice', cat='tea', drink=nm, tag='', sh='Чай', img='', hint='',
            q='При какой температуре заваривается?', opts=opts, ai=opts.index(t['temp']),
            sk=f'{nm}|температура|tea')
        extra_n += 1
    if t['spoons'].isdigit():
        add(t='num', cat='tea', drink=nm, tag='', sh='Чай', img='', hint='',
            q='Сколько ложек «1 tbsp» на порцию?', unit='ложк.', a=float(t['spoons']),
            sk=f'{nm}|ложки|tea')
        extra_n += 1
for m in extras['tea']['mixes']:
    for n, a in m['ing']:
        extra_n += ask_amount('tea', 'Чай', m['name'].strip(), n, a)

# --- заготовки: состав и выход
for x in extras['pf']:
    nm = x['name'].strip()
    for n, a in x['ing']:
        extra_n += ask_amount('pf', 'Заготовки (ПФ)', nm, n, a)
    if x['total']:
        p = parse_amount(x['total'])
        if p:
            add(t='num', cat='pf', drink=nm, tag='', sh='Заготовки (ПФ)', img='', hint='',
                q='Сколько получается на выходе?', unit=p[1], a=p[0], sk=f'{nm}|выход|pf')
            extra_n += 1

# --- подача: порции чистого алкоголя и топинги
for x in extras['serve']:
    nm = x['name'].strip()
    if '\n' in x['amount']:                       # спец. подача текилы: три строки сразу
        for line, label in zip(x['amount'].split('\n'), ['Текила', 'Лайм', 'Соль']):
            extra_n += ask_amount('serve', 'Подача', nm, label, line.strip())
        continue
    extra_n += ask_amount('serve', 'Подача', nm, 'порция', x['amount'])

print('кофе/чай/ПФ/подача:', extra_n)

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

# Блоки в drinks2.json лежат ровно в порядке книги: листы по порядку вкладок,
# внутри листа — по строке. Поэтому позиция в массиве и есть «порядок как в Excel».
SRC_ORDER = {d['name']: i for i, d in enumerate(drinks)}
SHEETS = []
for d in drinks:
    if d['sheet'] not in SHEETS:
        SHEETS.append(d['sheet'])

recipes, R_INDEX = [], {}
for ch in CHAPTERS:
    for nm in ch['items']:
        d = BYNAME[nm]
        R_INDEX[pretty(nm)] = len(recipes)
        recipes.append({
            'name': pretty(nm), 'ch': ch['id'],
            # порядок исходника: справочник умеет показывать карточки так же, как они идут
            # в Excel (лист + строка), а не только по главам пособия
            'sh': d['sheet'], 'si': SRC_ORDER[nm], 'tag': tag_of(d),
            'tech': TECH_FIX.get(nm, d['tech']), 'glass': GLASS_NORM.get(d['glass'], d['glass']),
            'straw': d['straw'], 'total': d['total'],
            'ing': [[n, a] for n, a in d['ing_main']],
            'gar': [[gar_label(n, a), a] for n, a in d['garnish']],
            'method': d['method'], 'serve': d['serve'],
            'formula': ' + '.join(f'{v} {n}' for v, n in d['formula']),
            'key': MNEMO.get(nm) or FAMILY_NOTE.get(nm, ''),
            'img': thumb(d['photos'][0] if d['photos'] else ''),
            'var': [{'name': pretty(v), 'method': BYNAME[v]['method']} for v in VARIANTS.get(nm, [])],
        })

for i, r in enumerate(recipes):       # карточки кофе, чая, ПФ и подачи
    R_INDEX.setdefault(r['name'], i)
for q in bank:                       # связываем вопрос с карточкой рецепта
    if q['drink'] in R_INDEX:
        q['r'] = R_INDEX[q['drink']]

# Стабильный id: позиция в массиве меняется при любой перегенерации банка, и тогда
# сохранённые ошибки «съезжали» на чужие вопросы. Хеш от напитка и текста вопроса
# переживает пересборку; меняется только если сам вопрос переформулирован.
import hashlib
seen = {}
for q in bank:
    q['id'] = hashlib.sha1(f"{q.get('sk','')}|{q['drink']}|{q['cat']}|{q['t']}|{q['q']}".encode()).hexdigest()[:10]
    seen.setdefault(q['id'], []).append(q['q'])
dupes = {k: v for k, v in seen.items() if len(v) > 1}
if dupes:
    raise SystemExit(f'Коллизия id вопросов: {dupes}')

# ------------------------------------------------- справочник посуды
# Отдельного листа с посудой в исходнике нет, поэтому собираем её из самих напитков:
# бокал -> какая трубочка -> что в нём подаётся. Никакой отсебятины, только связки из карточек.
GLASSWARE = {}
for r in recipes:
    g = r['glass']
    if not g: continue
    e = GLASSWARE.setdefault(g, {'name': g, 'straw': {}, 'drinks': [], 'img': ''})
    if r['straw']: e['straw'][r['straw']] = e['straw'].get(r['straw'], 0) + 1
    e['drinks'].append(r['name'])
    if not e['img']: e['img'] = r['img']
glassware = []
for g in sorted(GLASSWARE, key=lambda k: -len(GLASSWARE[k]['drinks'])):
    e = GLASSWARE[g]
    straws = sorted(e['straw'].items(), key=lambda kv: -kv[1])
    glassware.append({'name': e['name'], 'img': e['img'],
                      'straw': ' · '.join(k for k, _ in straws),
                      'n': len(e['drinks']), 'drinks': e['drinks']})

# Карточки для справочника: те же данные, что и в вопросах, чтобы после ошибки
# можно было открыть полную технологию, как у коктейлей.
CH_LIST.append({'id': 'extras', 'title': 'Кофе, чай, заготовки, подача',
                'color': '#8A6A4A', 'sub': 'Листы «Кофе», «Чай», «ПФ» и «Спец. подачи»'})
SHEETS += ['Кофе', 'Чай', 'Заготовки (ПФ)', 'Подача']

def extra_card(name, sheet, ing, total='', method='', chips=(), key=''):
    recipes.append({'name': name, 'ch': 'extras', 'sh': sheet, 'si': 10000 + len(recipes),
                    'tech': chips[0] if chips else '', 'glass': chips[1] if len(chips) > 1 else '',
                    'straw': chips[2] if len(chips) > 2 else '', 'total': total, 'tag': '',
                    'ing': [list(x) for x in ing], 'gar': [], 'method': method, 'serve': '',
                    'formula': '', 'key': key, 'img': '', 'var': []})

for c in extras['coffee']:
    chips = [x for x in ('эспрессо-машина', c['extract'], c['milk']) if x]
    extra_card(c['name'], 'Кофе', c['ing'], c['total'], c['method'], chips,
               ('Кнопка пролива: ' + c['button']) if c['button'] else '')
for t in extras['tea']['simple']:
    # заказчик просил: где доза меряется ложками, писать и количество ложек
    ing = [['Заварка', t['dose']]]
    if t['spoons'].isdigit():
        ing.append(['Ложек «1 tbsp»', t['spoons'] + ' шт'])
    extra_card(t['name'].strip(), 'Чай', ing, '', '', [t['temp']] if t['temp'] else [])
for m in extras['tea']['mixes']:
    extra_card(m['name'].strip(), 'Чай', m['ing'], '', m['method'])
for x in extras['pf']:
    extra_card(x['name'].strip(), 'Заготовки (ПФ)', x['ing'], x['total'], x['method'])
for x in extras['serve']:
    extra_card(x['name'].strip(), 'Подача', [['Порция', x['amount']]], '', x['rule'],
               [x['section'].capitalize()] if x['section'] else [])
for x in extras['straws']:
    extra_card(x['name'].strip(), 'Подача', [], '', x['rule'])

json.dump({'chapters': CH_LIST, 'sheets': SHEETS, 'glassware': glassware, 'recipes': recipes},
          open(f'{W}/data/recipes.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(MEDIA, open(f'{W}/data/media.json', 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(bank, open(f'{W}/data/bank.json', 'w', encoding='utf-8'), ensure_ascii=False)
from collections import Counter
print('вопросов:', len(bank), Counter((q['cat'], q['t']) for q in bank))
print('украшения: штук', piece_n, '· форм', form_n)
print('пак «пропущенная граммовка»:', fill_n, '· «впиши состав»:', mfill_n, '· метод:', method_n)
print('рецептов:', len(recipes), '· картинок:', len(MEDIA))
print('посуда:', glasses)
print('справочник посуды:', len(glassware), 'видов')
