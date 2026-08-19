# -*- coding: utf-8 -*-
"""30_pdf.py — печатает build/index.html в build/manual.pdf через headless Chromium.

ВАЖНО (грабли Chromium):
  * поля страницы задаём в CSS (@page{margin:0}) и печатаем с margin=0 —
    иначе полноформатная обложка обрезается по margin box;
  * любой элемент шире страницы включает shrink-to-fit и молча ужимает ВЕСЬ документ,
    поэтому в style.css есть глобальное img{max-width:100%};
  * номера страниц ставит следующий скрипт, а не footerTemplate.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / 'build' / 'index.html').as_uri()

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(src, wait_until='networkidle')
    pg.emulate_media(media='print')
    pg.pdf(path=str(ROOT / 'build' / 'manual.pdf'), format='A4', print_background=True,
           margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'},
           prefer_css_page_size=True)
    b.close()
print('build/manual.pdf готов')
