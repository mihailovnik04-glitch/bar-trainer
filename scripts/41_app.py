# -*- coding: utf-8 -*-
"""41_app.py — собирает тренажёр из quiz_template.html и data/*.json.

Выход:
  build/app/index.html — код, стили, шпаргалки (~35 КБ) — сюда идут все правки интерфейса
  build/app/media.js   — window.IMG: картинка хранится ОДИН раз по ключу ("image41")
  build/app/recipes.js — window.RECIPES: справочник (главы + карточки коктейлей)
  build/app/bank.js    — window.BANK: вопросы, ссылаются на картинку и рецепт по ключу/индексу
  build/quiz.html      — всё в одном файле, удобно переслать

Правки интерфейса делать в quiz_template.html, а не в build/ — build перезатирается.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
J = dict(ensure_ascii=False, separators=(',', ':'))

bank = json.load(open(ROOT / 'data' / 'bank.json'))
for q in bank:                       # выкидываем пустые поля
    for k in list(q):
        if q[k] in ('', None):
            del q[k]
bank_blob = json.dumps(bank, **J)
media_blob = json.dumps(json.load(open(ROOT / 'data' / 'media.json')), **J)
rec_blob = json.dumps(json.load(open(ROOT / 'data' / 'recipes.json')), **J)

tpl = (ROOT / 'quiz_template.html').read_text()
out = ROOT / 'build' / 'app'
out.mkdir(parents=True, exist_ok=True)

# --- версия из нескольких файлов
split = tpl.replace('<script id="bank" type="application/json">__BANK__</script>',
                    '<script src="bank.js"></script>')
split = split.replace("const BANK = JSON.parse(document.getElementById('bank').textContent);",
                      'const BANK = window.BANK;')
(out / 'index.html').write_text(split)
(out / 'media.js').write_text('window.IMG=' + media_blob + ';')
(out / 'recipes.js').write_text('window.RECIPES=' + rec_blob + ';')
(out / 'bank.js').write_text('window.BANK=' + bank_blob + ';')

# --- всё одним файлом
single = tpl.replace('<script src="media.js"></script>',
                     '<script>window.IMG=' + media_blob + ';</script>')
single = single.replace('<script src="recipes.js"></script>',
                        '<script>window.RECIPES=' + rec_blob + ';</script>')
single = single.replace('__BANK__', bank_blob)
(ROOT / 'build' / 'quiz.html').write_text(single)

kb = lambda s: f'{len(s)//1024} КБ'
print(f'index.html {kb(split)} · media.js {kb(media_blob)} · recipes.js {kb(rec_blob)} · '
      f'bank.js {kb(bank_blob)} · quiz.html {kb(single)}')
print(f'вопросов {len(bank)}, рецептов {len(json.loads(rec_blob)["recipes"])}')
