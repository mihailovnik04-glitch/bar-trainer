#!/usr/bin/env bash
# Полная сборка.
#   ./build.sh            обычная пересборка из готовых data/*.json
#   ./build.sh --full     + заново распарсить data/source.xlsx (нужен исходник)
#   ./build.sh --deploy   + положить тренажёр в docs/ и запушить на GitHub Pages
#   ./build.sh --vercel   + выкатить docs/ на Vercel (нужен vercel login один раз)
# Флаги можно совмещать: ./build.sh --full --deploy --vercel
set -e
cd "$(dirname "$0")"

# Интерпретатор: сначала venv проекта (Windows и Unix кладут его по-разному), потом системный.
if   [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ];        then PY=.venv/bin/python
elif command -v python3 >/dev/null;  then PY=python3
else echo 'Не найден Python. Создайте venv: python -m venv .venv && .venv/Scripts/pip install -r requirements.txt'; exit 1
fi
export PYTHONUTF8=1   # без него Windows читает json в cp1251 и портит кириллицу

FULL=; DEPLOY=; VERCEL=
for a in "$@"; do
  case "$a" in
    --full)   FULL=1 ;;
    --deploy) DEPLOY=1 ;;
    --vercel) VERCEL=1 ;;
    *) echo "Неизвестный флаг: $a"; exit 1 ;;
  esac
done

mkdir -p build

if [ -n "$FULL" ]; then
  $PY scripts/00_extract.py
  $PY scripts/01_parse.py > /dev/null
  $PY scripts/02_enrich.py > /dev/null
fi

$PY scripts/assemble.py      # data/*.json + scripts/pages*.py -> build/index.html
$PY scripts/30_pdf.py        # build/index.html -> build/manual.pdf
$PY scripts/31_stamp.py      # + номера страниц -> build/manual_final.pdf
$PY scripts/40_bank.py       # -> data/bank.json + thumb/
$PY scripts/41_app.py        # -> build/app/{index.html,bank.js} + build/quiz.html
$PY scripts/42_pwa.py        # -> build/app/{manifest.webmanifest,sw.js,icon-*.png}
$PY scripts/99_verify.py     # проверки; ненулевой код = сборка невалидна
echo "Готово: build/manual_final.pdf, build/app/, build/quiz.html"

if [ -n "$DEPLOY" ]; then
  rm -f docs/*
  cp build/app/* docs/
  git add -A docs/                       # add до проверки: новые файлы diff иначе не видит
  if git diff --cached --quiet -- docs/; then
    echo "Публикация: в docs/ ничего не изменилось, пуш не нужен."
  else
    git commit -q -m "тренажёр: пересборка $(date +%Y-%m-%d)"
    git push -q origin main
    echo "Опубликовано: https://mihailovnik04-glitch.github.io/bar-trainer/ (обновится за 1-2 минуты)"
  fi
fi

# Vercel раздаёт ту же папку docs/, что и Pages: сборка одна, площадки две.
if [ -n "$VERCEL" ]; then
  if ! vercel whoami >/dev/null 2>&1; then
    echo 'Vercel: сначала войдите — vercel login'; exit 1
  fi
  vercel deploy --prod --yes
fi
