#!/usr/bin/env bash
# Полная сборка. Шаги 00–02 нужны только если менялся исходный .xlsx.
set -e
cd "$(dirname "$0")"
mkdir -p build

if [ "$1" = "--full" ]; then
  python3 scripts/00_extract.py
  python3 scripts/01_parse.py > /dev/null
  python3 scripts/02_enrich.py > /dev/null
fi

python3 scripts/assemble.py      # data/*.json + scripts/pages*.py -> build/index.html
python3 scripts/30_pdf.py        # build/index.html -> build/manual.pdf
python3 scripts/31_stamp.py      # + номера страниц -> build/manual_final.pdf
python3 scripts/40_bank.py       # -> data/bank.json + thumb/
python3 scripts/41_app.py        # -> build/app/{index.html,bank.js} + build/quiz.html
python3 scripts/99_verify.py     # проверки; ненулевой код = сборка невалидна
echo "Готово: build/manual_final.pdf, build/app/, build/quiz.html"
