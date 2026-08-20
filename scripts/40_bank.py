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

import sys
sys.path.insert(0, f'{W}/scripts')
from config import CHAPTERS, MNEMO, FAMILY_NOTE, TECH_FIX
from morph import how_many, unit_word, genitive

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

GAR_FORMS_PCS = {}      # (продукт, штук) -> форма; для того, что меряется не в граммах

def _load_forms():
    rows = {r[0]: r[1:] for r in cells['Украшения']}
    for r0 in (1, 17, 33, 51, 67, 83):
        head, wline = rows.get(r0), rows.get(r0 + 1)
        if not head or not wline:
            continue
        for col in (1, 3, 5, 7):
            lab = re.sub(r'\s*\(на фото[^)]*\)', '', head[col - 1]).strip()
            if not lab or ' - ' not in lab:
                continue
            prod, _, form = lab.partition(' - ')
            m = re.search(r'(\d+[.,]?\d*)\s*гр', wline[col])
            if m:
                GAR_FORMS[(prod.strip().lower(), float(m.group(1).replace(',', '.')))] = form.strip()
                continue
            # «Бамбук лист - две половинки» весит не в граммах, а «1 шт»:
            # форма подачи от этого не перестаёт существовать
            m = re.match(r'^(\d+)\s*шт', wline[col].strip())
            if m:
                GAR_FORMS_PCS[(prod.strip().lower(), int(m.group(1)))] = form.strip()

_load_forms()
PLURAL = {'вейдж': 'вейджа', 'кольцо': 'кольца', 'полкольца': 'полукольца'}

def gar_form_pcs(name, amount):
    """'Бамбуковый лист', '1 шт' -> 'две половинки'. Для двух листов — «2 × две половинки»,
    потому что эталон описывает ровно один лист."""
    m = re.match(r'^(\d+)\s*шт', (amount or '').strip())
    if not m:
        return ''
    n, prod = int(m.group(1)), name.strip().lower()
    for (p_, base), form in GAR_FORMS_PCS.items():
        # в рецептах «Бамбуковый лист», в эталоне «Бамбук лист» — сверяем по корню слова
        a_, b_ = p_.split()[0], prod.split()[0]
        if not (a_.startswith(b_[:6]) or b_.startswith(a_[:6])) or base <= 0:
            continue
        if n == base:
            return form
        if n % base == 0:
            return f'{n // base} × {form}'
    return ''

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
    """Название украшения с формой нарезки: 'Лимон · вейдж', 'Бамбуковый лист · две половинки'."""
    base = clean_gar(name)
    f = gar_form(base, amount) or gar_form_pcs(base, amount)
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

# Шаг неверных вариантов у украшений задан по виду украшения — правила лежат
# в config.py, потому что по ним же 99_verify проверяет готовый банк.
from config import gar_steps

def distractors(v, unit, rnd, fine=False, steps=None):
    """3 неверных варианта. Обычно отклонение 10–40; у веса украшений шаг свой,
    по виду украшения (см. gar_steps): розмарин 4 гр против варианта 24 гр —
    не вопрос, а подарок."""
    out = []
    tries = 0
    if steps is None:
        steps = [1, 2, 3] if fine else None
    while len(out) < 3 and tries < 400:
        tries += 1
        d = rnd.choice(steps or steps_for(v)) * rnd.choice([-1, 1])
        cand = round(v + d, 1)
        if cand <= 0: continue
        if steps is None and not fine and v >= 100: cand = round(cand / 5) * 5
        if cand == v or cand in out: continue
        if steps is None and not fine and abs(cand - v) < 10: continue
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

# ------------------------------------------------- сеты шотов
# «Сет из 4 шотов» написано в первой строке способа приготовления — единственное место,
# где количество шотов вообще указано. Нужно для двух вещей: понять, что это шоты
# (б/А сет «Нулевой пациент 0,0» лежит на листе «Лимонады и БА», и в фильтре «Шотики»
# его не было), и посчитать украшение на один шот против всего сета.
WORD_N = {'двух': 2, 'трех': 3, 'трёх': 3, 'четырех': 4, 'четырёх': 4,
          'пяти': 5, 'шести': 6, 'восьми': 8}
SHOT_RE = re.compile(r'сет\s+из\s+(\d+|[а-яё]+)\s+([а-яё\s]*?)шот', re.I)
# «пара №1», «пара №2» — строки-разделители внутри «В Питере — пить!»: сет собран
# из трёх пар, и у каждой пары свой состав и своё украшение.
PART_RE = re.compile(r'^пара\s*№\s*\d+$', re.I)

def shots_of(d):
    """Сколько шотов в сете. 0 — если это не сет."""
    m = SHOT_RE.search(d.get('method') or '')
    if not m:
        return 0
    raw = m.group(1)
    n = int(raw) if raw.isdigit() else WORD_N.get(raw.lower().replace('ё', 'е'), 0)
    if 'пар' in (m.group(2) or '').lower():   # «сет из трёх ПАР шотов» — это шесть штук
        n *= 2
    return n

def parts_of(d):
    """Сколько частей («пара №N») внутри сета. 0 — сет неделимый."""
    return sum(1 for n, _ in d['ing'] if PART_RE.match(n.strip()))

# Вид напитка в фильтрах тренажёра — не всегда лист исходника: сет шотов остаётся
# шотами, на каком бы листе он ни лежал. В справочнике лист настоящий, там порядок
# «как в Excel», и трогать его нельзя.
def kind_sheet(d):
    if d['sheet'] == 'Шотики':
        return 'Шотики'
    if shots_of(d) or str(d.get('glass') or '').startswith('Шоты'):
        return 'Шотики'
    return d['sheet']

for d in drinks:
    if 'Безо льда' in d['name']:
        continue
    nm = pretty(d['name'])
    tg = tag_of(d)
    sh = kind_sheet(d)
    nshots = shots_of(d)
    nparts = parts_of(d)
    # Сколько шотов приходится на одну часть сета: у «В Питере — пить!» это пара,
    # то есть 2 шота, и украшение в её строке относится именно к паре, а не ко всем шести.
    part_shots = (nshots // nparts) if (nparts and nshots and nshots % nparts == 0) else 0
    im = thumb(d['photos'][0] if d['photos'] else '')
    seen = {}
    for n, a in d['ing']:
        seen[n] = seen.get(n, 0) + 1
    # Один и тот же продукт может идти и в состав, и на украшение — с разными весами
    # (розмарин во взваре: 3 гр внутрь, 4 гр сверху). Суммировать их нельзя, поэтому
    # такие строки спрашиваем раздельно и обязательно уточняем, о чём речь.
    both = {clean_gar(n).lower() for n, _ in d['ing'] if 'укр' in n.lower()} &            {n.strip().lower() for n, _ in d['ing'] if 'укр' not in n.lower()}

    def pair(v, unit, sk, q, cat, hint='', img=None, steps=None, fine=False):
        """Один и тот же факт двумя способами: точный ввод и выбор из четырёх.
        Раньше кидали монетку 60/40, и половина граммовок точным вводом не спрашивалась
        вовсе — заказчик просил, чтобы спрашивалось всё и во всех комбинациях.
        В одну сессию оба не попадут: dedupe схлопывает их по общему sk."""
        kw = dict(cat=cat, drink=nm, tag=tg, sh=sh, q=q, hint=hint,
                  img=im if img is None else img, sk=sk)
        add(t='num', unit=unit, a=v, **kw)
        opts = distractors(v, unit, rnd, fine=fine, steps=steps) + [v]
        rnd.shuffle(opts)
        add(t='choice', opts=[f'{fmtnum(o)} {unit}' for o in opts], ai=opts.index(v), **kw)

    def ask(n, a, is_gar, part=''):
        p = parse_amount(a)
        if not p: return
        v, unit, hint = p
        label = clean_gar(n)
        dual = label.lower() in both
        head = how_many(unit, label)
        # Сколько шотов покрывает эта строка: у делимого сета — своя часть, иначе весь сет
        cover = part_shots if (part and part_shots) else nshots
        cover_txt = (f'{part.replace("пара", "пары")} ({cover} шота)' if part and part_shots
                     else f'всего сета из {cover} шотов')
        if is_gar:
            # Форму нарезки и количество штук из вопроса про вес убрали (просьба 20.08.2026):
            # «сколько граммов лимона» — вопрос, «сколько граммов Лимон · 2 вейджа» — ответ.
            hint = ''            # «указано как 4 шт - 8 гр» тоже просили убрать
            if cover:
                # У сета вес украшения в таблице указан на весь сет (а у «В Питере» —
                # на свою пару). Молча спрашивать «сколько» — значит спрашивать неизвестно
                # что, поэтому охват пишем всегда явно.
                q = f'{head} идёт на украшение {cover_txt}?'
            else:
                q = (f'{head} идёт ТОЛЬКО на украшение?' if dual
                     else f'{head} идёт на украшение?')
            pair(v, unit, f'{nm}|{label}|g', q, 'garnish', hint=hint,
                 steps=gar_steps(label, v), fine=(unit == 'гр' and v <= 30))
            # ...и второй вопрос — на один шот, но только когда деление даёт величину,
            # которую действительно отмеряют. 2 гр мяты на 4 шота = 0,5 гр в шот — так
            # никто не работает, такой вопрос не задаём.
            if cover:
                per = v / cover
                if per >= 1 and float(per).is_integer():
                    pair(per, unit, f'{nm}|{label}|gone',
                         f'{head} идёт на украшение ОДНОГО шота?', 'garnish',
                         steps=gar_steps(label, per), fine=(unit == 'гр' and per <= 30))
            return
        q = (f'{head} идёт в состав, не считая украшения?' if dual else f'{head}?')
        pair(v, unit, f'{nm}|{label}|i', q, 'grams', hint=hint)

    part = ''
    for n, a in d['ing']:
        if PART_RE.match(n.strip()):     # строка-разделитель, а не ингредиент
            part = n.strip().lower()
            continue
        if seen[n] > 1:      # неоднозначные повторы (напр. водка в двух парах шотов)
            continue
        ask(n, a, 'укр' in n.lower(), part)

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
        pair(total_v, unit, f'{nm}|{label}|sum',
             f'{how_many(unit, label)} уходит на напиток ВСЕГО — и в состав, и на украшение?',
             'grams')

    # --- сколько граммов украшений уходит на напиток целиком
    # Заказчик просил это для «В Питере — пить!», но правило общее: где украшений
    # больше одного и все они в граммах, сумма — такой же проверяемый факт.
    gar_g = [parse_amount(a) for n, a in d['ing'] if 'укр' in n.lower()]
    gar_g = [p for p in gar_g if p and p[1] == 'гр']
    if len(gar_g) >= 2:
        tot_g = sum(p[0] for p in gar_g)
        q_all = (f'Сколько граммов украшений уходит на весь сет из {nshots} шотов?'
                 if nshots else 'Сколько граммов украшений уходит на напиток целиком?')
        pair(tot_g, 'гр', f'{nm}|украшения|garsum', q_all, 'garnish')

    # --- сколько жидкости наливается всего
    # У сетов шотов состав расписан по парам, и «выход» ощущается как что-то отдельное
    # от суммы. Спрашиваем прямо: сколько всего налито.
    liq_all = [parse_amount(a) for n, a in d['ing'] if 'укр' not in n.lower()]
    liq_all = [p for p in liq_all if p and p[1] == 'мл']
    if nshots and len(liq_all) >= 3:
        pair(sum(p[0] for p in liq_all), 'мл', f'{nm}|жидкость|liqsum',
             f'Сколько миллилитров жидкости наливается на весь сет из {nshots} шотов?',
             'grams')

    # --- посуда (немного, только характерная). Картинку не показываем:
    # по фото бокал угадывается без знания рецептуры.
    gl = GLASS_NORM.get(d['glass'], d['glass'])
    if gl not in GLASS_SKIP and gl in GLASS_RARE:
        add(t='glass', cat='glass', drink=nm, tag=tg, sh=sh, img='',
            q='В какой посуде подаётся напиток?', ans=gl, sk=f'{nm}|glass')
    # --- чем украшается. Картинку тут не показываем: на фото украшение видно целиком,
    # и вопрос превращается в «посмотри на снимок» (просьба 20.08.2026).
    gars = [gar_label(n, a) for n, a in d['ing'] if 'укр' in n.lower()]
    if len(gars) >= 2:
        add(t='garset', cat='garnish', drink=nm, tag=tg, sh=sh, img='',
            q='Чем украшается напиток?', ans=' + '.join(gars), sk=f'{nm}|garset')

# Правило нарезки бамбука лежит на листе «ПФ» отдельной строкой-инструкцией.
# Берём его дословно и показываем подсказкой к вопросу — иначе «1 шт» ничего не говорит
# о том, целым листом украшать или половинками.
def _bamboo_rule():
    for row in cells['ПФ']:
        cellsr = [c.strip() for c in row[1:] if c.strip()]
        if cellsr and 'бамбук' in cellsr[0].lower() and 'порезать' in cellsr[0].lower():
            return '. '.join(c.rstrip('.') for c in cellsr) + '.'
    return ''

BAMBOO_RULE = _bamboo_rule()

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
    nm, tg, sh = pretty(d['name']), tag_of(d), kind_sheet(d)
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
        # Украшение спрашиваем в граммах везде, где граммовка есть в исходнике;
        # вопрос «сколько штук» остаётся только там, где граммов нет вовсе.
        # Из такого чисто штучного нужен лишь бамбуковый лист: зонтик, наклейка,
        # пергамент и сахарные картинки — сборка подачи, а не рецептура.
        if 'гр' in a or 'бамбук' not in label.lower():
            continue
        others = [c for c in PIECE_POOL if c != cnt]
        rnd.shuffle(others)
        opts = others[:3] + [cnt]
        if len(opts) < 4:
            continue
        rnd.shuffle(opts)
        add(t='choice', cat='garnish', drink=nm, tag=tg, sh=sh, img=im,
            hint=(BAMBOO_RULE if 'бамбук' in label.lower() else ''),
            # В самом вопросе только название: форма вида «2 × две половинки»
            # выдавала бы ответ. Правило нарезки уходит в подсказку.
            q=(f'{how_many("шт", label)} идёт на украшение всего сета из {shots_of(d)} шотов?'
               if shots_of(d) else f'{how_many("шт", label)} идёт на украшение?'),
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
    nm, tg, sh = pretty(d['name']), tag_of(d), kind_sheet(d)
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
TECHS = ['Билд', 'Шейк', 'Стир', 'Блендер', 'Питчер', 'Слоями']
# Билд и Стир в одном наборе вариантов — ловушка, а не вопрос: чтобы охладить билд,
# бармен фактически стирует, и выбрать «правильный» из этой пары нельзя (просьба 20.08.2026).
# Стир остаётся только там, где он прямо написан в исходнике, и никогда не соседствует с билдом.
CONFUSING = {('Билд', 'Стир'), ('Стир', 'Билд')}
method_n = 0
for i, d in enumerate(drinks):
    if 'Безо льда' in d['name'] or i % 5:
        continue
    # d['tech'] распознан регуляркой и в трёх местах ошибается: у «Рафунтеллы» написано
    # «взбить» (пароотвод, а не шейкер), у «Бамбла» и «Криспи Айс Латте» упомянут питчер.
    # Правильные значения лежат в TECH_FIX — вопрос обязан брать их, как и справочник.
    nm = pretty(d['name'])
    tech = TECH_FIX.get(d['name'], d['tech'])
    if tech not in TECHS:
        continue
    # Билд и Стир не должны оказаться в одном наборе НИ ПРИ КАКОМ правильном ответе:
    # даже когда верен «Питчер», пара «Билд / Стир» среди вариантов сбивает с толку.
    others, picked = [t for t in TECHS if t != tech], []
    rnd.shuffle(others)
    for t in others:
        if CONFUSING & {(t, x) for x in picked + [tech]}:
            continue
        picked.append(t)
        if len(picked) == 3:
            break
    if len(picked) < 3:
        continue
    opts = picked + [tech]
    rnd.shuffle(opts)
    add(t='choice', cat='method', drink=nm, tag=tag_of(d), sh=kind_sheet(d),
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
        # Тот же эталон ещё раз выбором, с шагом по виду украшения: у вейджа он пятёрками,
        # у зелени — граммами, иначе неверные варианты видно не глядя.
        opts = distractors(v, unit, rnd, fine=True,
                           steps=gar_steps(label.partition(' - ')[0], v)) + [v]
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
    """Величина двумя способами сразу: точный ввод и выбор из четырёх.
    Общий sk у обоих — dedupe не пустит их в одну сессию, но спросить может любой."""
    p = parse_amount(amount)
    if not p:
        return 0
    v, unit, hint = p
    fine = unit == 'гр' and v <= 30
    q = f'{how_many(unit, label)}?'
    kw = dict(cat=cat, drink=who, tag='', sh=sheet, img=im, hint=hint,
              sk=f'{who}|{label}|{extra_sk or cat}')
    add(t='num', q=q, unit=unit, a=v, **kw)
    # gar_steps здесь не применяем: классы «вейдж/ягода/зелень» относятся к украшениям,
    # а тут кофе, чай и заготовки. Иначе «Конфитюр Лимон» ловил бы шаг цитрусов
    # и получал варианты 100/105/95 мл — вопрос без вопроса.
    opts = distractors(v, unit, rnd, fine=fine) + [v]
    rnd.shuffle(opts)
    add(t='choice', q=q, opts=[f'{fmtnum(o)} {unit}' for o in opts], ai=opts.index(v), **kw)
    return 2

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
# «Таежный Микс» и «Фруктовый Пунш» есть на листе «Чай» дважды: простой засыпкой
# (12 и 15 гр) и крафтовой смесью. В баре готовят только крафт, поэтому простые версии
# из тренажёра и справочника убраны (просьба заказчика 20.08.2026). В исходнике они
# остаются как есть — данные мы не правим.
TEA_SKIP = {'таежный микс', 'фруктовый пунш'}
tea_simple = [t for t in extras['tea']['simple']
              if t['name'].strip().lower().replace('ё', 'е') not in TEA_SKIP]

TEMPS = sorted({t['temp'] for t in tea_simple if t['temp']})
for t in tea_simple:
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

# В чём выносить — такой же проверяемый факт, как граммовка. Варианты берём
# из реальных ответов других строк подачи.
WARES = sorted({x['ware'] for x in extras['serve'] if x.get('ware')})
for x in extras['serve']:
    w = x.get('ware')
    if not w or len(WARES) < 4:
        continue
    others = [o for o in WARES if o != w]
    rnd.shuffle(others)
    opts = others[:3] + [w]
    rnd.shuffle(opts)
    add(t='choice', cat='serve', drink=x['name'].strip(), tag='', sh='Подача', img='', hint='',
        q='В чём выносится Гостю?', opts=opts, ai=opts.index(w),
        sk=f"{x['name'].strip()}|посуда|serve")
    extra_n += 1

print('кофе/чай/ПФ/подача:', extra_n)

# ------------------------------------------------- справочник для приложения
CH_OF, CH_LIST = {}, []
for ch in CHAPTERS:
    CH_LIST.append({'id': ch['id'], 'title': ch['title'], 'color': ch['color'], 'sub': ch['sub']})
    for nm in ch['items']:
        CH_OF[nm] = ch['id']

def calc_ml(d):
    """Выход, посчитанный как сумма жидкостей. Нужен вариантам «Безо льда»: в таблице
    у них выход не проставлен вовсе. Помечаем «≈», чтобы не путать с цифрой из исходника."""
    if d['total']:
        return d['total']
    s = 0.0
    for n, a in d['ing']:
        if 'укр' in n.lower():
            continue
        m = re.match(r'^(\d+[.,]?\d*)\s*мл\.?$', a.strip())
        if m:
            s += float(m.group(1).replace(',', '.'))
    return f'≈ {fmtnum(s)} мл' if s else ''

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
            'var': [{'name': pretty(v), 'method': BYNAME[v]['method'],
                     'total': calc_ml(BYNAME[v])} for v in VARIANTS.get(nm, [])],
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
for t in tea_simple:
    # заказчик просил: где доза меряется ложками, писать и количество ложек
    ing = [['Заварка', t['dose']]]
    if t['spoons'].isdigit():
        ing.append(['Ложек «1 tbsp»', t['spoons'] + ' шт'])
    note = t.get('full', '')
    extra_card(t['name'].strip(), 'Чай', ing, '',
               note if note != t['name'].strip() else '',
               [t['temp']] if t['temp'] else [])
for m in extras['tea']['mixes']:
    extra_card(m['name'].strip(), 'Чай', m['ing'], '', m['method'])
for x in extras['pf']:
    extra_card(x['name'].strip(), 'Заготовки (ПФ)', x['ing'], x['total'], x['method'])
for x in extras['serve']:
    rows = [['Порция', x['amount']]]
    if x.get('ware'):
        rows.append(['Посуда', x['ware']])
    extra_card(x['name'].strip(), 'Подача', rows, '', x['rule'],
               [c for c in (x['section'].capitalize() if x['section'] else '', x.get('ware', '')) if c])
# Трубочки своих карточек не получают: заказчик просил не выносить их в справочник
# отдельно — они и так подписаны у каждого коктейля.

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
