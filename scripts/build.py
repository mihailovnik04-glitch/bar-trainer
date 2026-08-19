# -*- coding: utf-8 -*-
import json, re, base64, os, html
from config import CHAPTERS, MNEMO, TECH_FIX, FAMILY_NOTE

from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
W = str(ROOT)
drinks = json.load(open(f'{W}/data/drinks2.json', encoding='utf-8'))
imgs = json.load(open(f'{W}/data/images.json', encoding='utf-8'))
cells = json.load(open(f'{W}/data/data.json', encoding='utf-8'))
BY = {}
for d in drinks:
    d['tech'] = TECH_FIX.get(d['name'], d['tech'])
    BY[d['name']] = d

# ---------------------------------------------------------------- helpers
_cache = {}
def img(path, cls='', alt=''):
    """media/imageNN.png -> <img> с base64"""
    if not path: return ''
    base = os.path.splitext(os.path.basename(path))[0] + '.jpg'
    f = f'{W}/img/{base}'
    if not os.path.exists(f): return ''
    if f not in _cache:
        _cache[f] = base64.b64encode(open(f, 'rb').read()).decode()
    return f'<img class="{cls}" alt="{html.escape(alt)}" src="data:image/jpeg;base64,{_cache[f]}">'

def esc(s): return html.escape(s or '')

def fonts_css():
    out = []
    fam = [('Inter', 'fontsource-inter/files/inter-cyrillic-%s-normal.woff2', [400, 500, 600, 700]),
           ('Manrope', 'fontsource-manrope/files/manrope-cyrillic-%s-normal.woff2', [500, 600, 700, 800]),
           ('JetBrains Mono', 'fontsource-jetbrains-mono/files/jetbrains-mono-cyrillic-%s-normal.woff2', [400, 500, 600, 700]),
           ('Playfair Display', 'fontsource-playfair-display/files/playfair-display-cyrillic-%s-normal.woff2', [400, 500])]
    for name, tpl, weights in fam:
        for wt in weights:
            p = f'{W}/fonts/' + tpl % wt
            if not os.path.exists(p): continue
            b = base64.b64encode(open(p, 'rb').read()).decode()
            out.append(f"@font-face{{font-family:'{name}';font-style:normal;font-weight:{wt};"
                       f"src:url(data:font/woff2;base64,{b}) format('woff2');font-display:block;}}")
    return '\n'.join(out)

def markup_method(t):
    """выделяем ключевые действия и числа"""
    t = esc(t).replace('\n', '<br>')
    for w in ['Взбить', 'взбить', 'Перемешать', 'перемешать', 'Отфильтровать', 'отфильтровать',
              'Украсить', 'украсить', 'Прогреть', 'прогреть', 'Охладить', 'охладить',
              'размять мадлером', 'слить талую воду', 'не варить', 'проварить', 'Стир', 'слоями',
              'не перемешивать', 'Подается не перемешанным', 'Подается слоистым']:
        t = re.sub(r'(?<![>\w])' + re.escape(w) + r'(?![\w<])', f'<b>{w}</b>', t)
    return t

def chips(d):
    c = [f'<span class="chip acc">{esc(d["tech"])}</span>']
    if d['glass']: c.append(f'<span class="chip">{esc(d["glass"])}</span>')
    if d['straw']: c.append(f'<span class="chip">{esc(d["straw"])}</span>')
    return ''.join(c)

def ing_table(d):
    rows = []
    for n, a in d['ing_main']:
        rows.append(f'<tr><td class="n">{esc(n)}</td><td class="a">{esc(a)}</td></tr>')
    if d['garnish']:
        rows.append('<tr class="sub"><td colspan="2"><span>Украшение</span></td></tr>')
        for n, a in d['garnish']:
            nn = re.sub(r'\s*укр\.?\s*\*?$', '', n.strip())
            rows.append(f'<tr class="g"><td class="n">{esc(nn)}</td><td class="a">{esc(a)}</td></tr>')
    return '<table class="ing">' + ''.join(rows) + '</table>'

def formula_line(d):
    if not d['formula']: return ''
    parts = ' + '.join(f'<b>{v}</b> {n}' for v, n in d['formula'])
    tot = d['total']
    return f'<div class="formula">{parts}{" = <b>" + esc(tot) + "</b>" if tot else ""}</div>'

def card(name):
    d = BY[name]
    photo = d['photos'][0] if d['photos'] else ''
    key = MNEMO.get(name) or FAMILY_NOTE.get(name) or ''
    ph = f'<div class="ph">{img(photo, alt=name)}</div>' if photo else ''
    title = re.sub(r'\s*/\s*', ' · ', name)
    keyhtml = f'<div class="key"><b>Ключ</b>{esc(key)}</div>' if key else ''
    serve = f'<div class="serve">{esc(d["serve"])}</div>' if d['serve'] else ''
    return f'''<article class="card" data-s="{esc(name.lower())} {esc(' '.join(n.lower() for n,_ in d['ing']))}">
  {ph}
  <div class="body">
    <div class="head"><h3>{esc(title)}</h3>{f'<span class="vol">{esc(d["total"])}</span>' if d['total'] else ''}</div>
    <div class="chips">{chips(d)}</div>
    <div class="cols">
      <div class="col-ing"><div class="lbl">Состав</div>{ing_table(d)}</div>
      <div class="col-m"><div class="lbl">Приготовление</div><div class="method">{markup_method(d['method'])}</div>{serve}</div>
    </div>
    {formula_line(d)}
    {keyhtml}
  </div>
</article>'''

def variant_block(name):
    d = BY[name]
    title = re.sub(r'\s*/\s*', ' · ', name)
    return f'''<div class="variant" data-s="{esc(name.lower())}">
  <h4>{esc(title)}</h4>
  <div class="method">{markup_method(d['method'])}</div>
</div>'''

VARIANTS = {}   # родитель -> [имена вариантов]
for d in drinks:
    if 'Безо льда' in d['name']:
        parent = d['name'].split(' / Безо льда')[0]
        VARIANTS.setdefault(parent, []).append(d['name'])

# ---------------------------------------------------------------- справочные листы
def sheet_rows(name):
    """{row: {col: value}}"""
    out = {}
    for row in cells[name]:
        r = row[0]
        out[r] = {i + 1: v for i, v in enumerate(row[1:]) if v.strip()}
    return out

def parse_blocks(sheet, name_col=1, ing_col=2, amt_col=3, txt_col=4):
    rows = sheet_rows(sheet)
    blocks = []
    cur = None
    prev_name = False
    for r in sorted(rows):
        c = rows[r]
        n = c.get(name_col, '').strip()
        ing = c.get(ing_col, '').strip()
        amt = c.get(amt_col, '').strip()
        txt = c.get(txt_col, '').strip()
        if n:
            if cur is None or not prev_name:
                cur = dict(name=n, ing=[], steps=[], total='', row0=r)
                blocks.append(cur)
            else:
                cur['name'] += ' ' + n
        prev_name = bool(n)
        if cur is None: continue
        cur['row1'] = r
        if ing and amt: cur['ing'].append((ing, amt))
        elif ing: cur['ing'].append((ing, ''))
        elif amt: cur['total'] = amt
        if txt: cur['steps'].append(txt)
    return blocks

def block_photo(sheet, b, col_max=9):
    for i in imgs.get(sheet, []):
        if b['row0'] <= i['row'] <= b.get('row1', b['row0']) and i['col'] <= col_max:
            return i['file']
    return ''

def rcard(title, badges, steps, photo='', ing=None, note=''):
    b = ''.join(f'<span class="{"o" if o else ""}">{esc(t)}</span>' for t, o in badges)
    ings = ''
    if ing:
        ings = '<table class="ing">' + ''.join(
            f'<tr><td class="n">{esc(n)}</td><td class="a">{esc(a)}</td></tr>' for n, a in ing) + '</table>'
    st = ''.join(f'<li>{markup_method(s)}</li>' for s in steps)
    im = f'<div class="rim">{img(photo, alt=title)}</div>' if photo else ''
    return f'''<div class="rcard">{im}<div style="flex:1;min-width:0">
      <h4>{esc(title)}</h4><div class="rows">{b}</div>
      {'<div class="cols"><div class="col-ing">' + ings + '</div><div class="col-m"><ol>' + st + '</ol></div></div>' if ings else '<ol>' + st + '</ol>'}
      {f'<div class="note">{esc(note)}</div>' if note else ''}
    </div></div>'''
