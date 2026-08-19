# -*- coding: utf-8 -*-
import os, re
from build import (drinks, BY, CHAPTERS, VARIANTS, card, variant_block, fonts_css, esc)
from pages import system_pages
from pages2 import coffee_html, tea_html, pf_html, garnish_html, standards_html

from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
W = str(ROOT)
CSS = open(f'{W}/style.css').read()

REF = [
    dict(id='coffee', num='12', title='Кофе', sub='Матрица напитков и технология эспрессо-бара',
         color='#6B4A34', pages=coffee_html()),
    dict(id='tea', num='13', title='Чай', sub='Дозировки, температуры и правила подачи',
         color='#3E6F62', pages=tea_html()),
    dict(id='pf', num='14', title='Полуфабрикаты', sub='ПФ, кордиалы, нарезка и эталон сахарного сиропа',
         color='#3A5A8C', pages=pf_html()),
    dict(id='garnish', num='15', title='Украшения и трубочки', sub='Эталонный вес и вид каждого элемента',
         color='#D08A2C', pages=garnish_html()),
    dict(id='std', num='16', title='Стандарты подачи', sub='Чистый алкоголь, топинги, напитки с собой',
         color='#4A4E58', pages=standards_html()),
]

def divider(ch, first=False):
    return f'''<div class="divider{' first' if first else ''}" id="{ch['id']}">
  <div class="num">Глава {ch['num']}</div>
  <h2>{esc(ch['title'])}</h2>
  <div class="rule"></div>
  <p>{esc(ch['sub'])}</p>
</div>'''

def build_html():
    all_ch = [dict(id='system', num='01', title='Система', sub='Правила, формулы и мнемотехники, на которых держится всё меню', color='#B8452F')]
    all_ch += CHAPTERS + REF

    # ---------- обложка
    strip = ''.join(f'<i style="background:{c["color"]}"></i>' for c in all_ch)
    n_drinks = len([d for d in drinks if 'Безо льда' not in d['name']])
    cover = f'''<section class="cover page">
  <div>
    <div class="kicker">Барное пособие · Технологические карты</div>
    <div class="cover-strip">{strip}</div>
  </div>
  <div>
    <h1>Бар<br><em>от формулы<br>к напитку</em></h1>
    <p class="lead">Полная раскладка меню: состав, граммовки, украшения и способ приготовления —
    без единого изменения. Плюс закономерности, которые превращают {n_drinks} рецептов
    в десяток простых правил.</p>
    <div class="cover-grid">
      <div><b>{n_drinks}</b><span>рецептов</span></div>
      <div><b>16</b><span>глав</span></div>
      <div><b>5</b><span>техник</span></div>
      <div><b>1</b><span>формула выхода</span></div>
    </div>
  </div>
  <div class="kicker">Обновление от 07.07.26 · внутренний документ</div>
</section>'''

    # ---------- содержание
    items = ''.join(f'''<a class="toc-item" href="#{c['id']}"><b>{c['num']}</b>
        <i style="background:{c['color']}"></i><span>{esc(c['title'])}</span></a>''' for c in all_ch)
    toc = f'''<section class="page toc">
  <h2>Содержание</h2>
  <div class="toc-list">{items}</div>
  <div class="box tint" style="--acc:#B8452F;--acc-soft:#F6EDE7;margin-top:8mm">
    <div class="lbl">Как читать карточку напитка</div>
    <ul class="clean">
      <li><b>Чипы под названием</b> — техника, посуда и трубочка. Три вещи, которые спрашивают чаще всего.</li>
      <li><b>Состав</b> — точные граммовки; украшения вынесены отдельным блоком внизу.</li>
      <li><b>Формула</b> — та же рецептура в одну строку. Учить удобнее именно её.</li>
      <li><b>Ключ</b> — мнемоника: симметрии, лестницы чисел и подсказки из названия.</li>
    </ul>
  </div>
</section>'''

    parts = [cover, toc]

    # ---------- глава 01
    ch = all_ch[0]
    parts.append(f'<section class="page sheet" style="--acc:{ch["color"]};--acc-soft:{ch["color"]}14">'
                 + divider(ch, first=True) + '\n'.join(system_pages()) + '</section>')

    # ---------- главы с карточками
    for ch in CHAPTERS:
        body = [divider(ch)]
        for nm in ch['items']:
            if nm not in BY:
                raise SystemExit('НЕТ НАПИТКА: ' + nm)
            body.append(card(nm))
            for v in VARIANTS.get(nm, []):
                body.append(variant_block(v))
        parts.append(f'<section class="page sheet" style="--acc:{ch["color"]};--acc-soft:{ch["color"]}14">'
                     + '\n'.join(body) + '</section>')

    # ---------- справочные главы
    for ch in REF:
        pages = ch['pages']
        parts.append(f'<section class="page sheet" style="--acc:{ch["color"]};--acc-soft:{ch["color"]}14">'
                     + divider(ch) + pages[0] + '</section>')
        for p in pages[1:]:
            parts.append(f'<section class="page sheet" style="--acc:{ch["color"]};--acc-soft:{ch["color"]}14">{p}</section>')

    nav = ''.join(f'<a href="#{c["id"]}">{esc(c["title"])}</a>' for c in all_ch)
    html = f'''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Барное пособие · от формулы к напитку</title>
<style>{fonts_css()}
{CSS}</style></head><body>
<div id="nav" class="screen-only"><div class="inner"><b>Барное пособие</b>{nav}
<input id="q" placeholder="Поиск по напитку или ингредиенту…"></div></div>
{''.join(parts)}
<script>
const q=document.getElementById('q');
q&&q.addEventListener('input',()=>{{
  const v=q.value.trim().toLowerCase();
  document.querySelectorAll('.card,.variant').forEach(el=>{{
    el.classList.toggle('hidden', !!v && !(el.dataset.s||'').includes(v));
  }});
}});
</script>
</body></html>'''
    return html

if __name__ == '__main__':
    (ROOT/'build').mkdir(exist_ok=True)
    h = build_html()
    open(f'{W}/build/index.html', 'w').write(h)
    print('html', round(len(h) / 1e6, 2), 'MB')
