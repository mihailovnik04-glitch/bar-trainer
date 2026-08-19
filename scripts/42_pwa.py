# -*- coding: utf-8 -*-
"""42_pwa.py — PWA-обвязка для build/app: манифест, service worker, иконки.

Нужна только многофайловой версии (build/app -> docs/), которую раздаёт GitHub Pages:
после первой загрузки тренажёр открывается офлайн и ставится на домашний экран.
Одиночный build/quiz.html остаётся действительно одиночным — его никто не «устанавливает».

Service worker кеширует всё приложение целиком (в сумме ~1,5 МБ) и отдаёт из кеша.
Имя кеша содержит хеш от содержимого: новая сборка = новое имя = старый кеш выбрасывается,
поэтому обновление доезжает до телефона само, без «очистить данные сайта».
"""
import hashlib, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / 'build' / 'app'
BG, ACC = '#0F0D0B', '#E0A45B'
FILES = ['index.html', 'bank.js', 'recipes.js', 'media.js', 'manifest.webmanifest']

MANIFEST = {
    'name': 'Тренажёр Tokyo-City',
    'short_name': 'Tokyo-City',
    'description': 'Тренажёр и база знаний Tokyo-City: технологические карты бара, '
                   'граммовки, украшения и посуда',
    'start_url': './',
    'scope': './',
    'display': 'standalone',
    'orientation': 'portrait',
    'background_color': BG,
    'theme_color': '#17140F',
    'lang': 'ru',
    'icons': [{'src': f'icon-{s}.png', 'sizes': f'{s}x{s}', 'type': 'image/png',
               'purpose': 'any maskable'} for s in (192, 512)],
}


def font(size):
    for p in ('C:/Windows/Fonts/segoeuib.ttf', 'C:/Windows/Fonts/arialbd.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def icon(size):
    """Рюмка на тёмном фоне. Maskable — значит рисунок держим внутри центральных 80%."""
    im = Image.new('RGB', (size, size), BG)
    d = ImageDraw.Draw(im)
    u = size / 100                                   # работаем в процентах от стороны
    d.rounded_rectangle([6 * u, 6 * u, 94 * u, 94 * u], radius=22 * u, fill='#191612')
    d.polygon([(30 * u, 30 * u), (70 * u, 30 * u), (50 * u, 58 * u)], fill=ACC)   # чаша
    d.rectangle([48.5 * u, 58 * u, 51.5 * u, 74 * u], fill=ACC)                   # ножка
    d.rounded_rectangle([36 * u, 73 * u, 64 * u, 77 * u], radius=2 * u, fill=ACC)  # основание
    d.ellipse([62 * u, 22 * u, 72 * u, 32 * u], fill='#4FB477')                    # «оливка»
    im.save(APP / f'icon-{size}.png')


for s in (192, 512):
    icon(s)
(APP / 'manifest.webmanifest').write_text(
    json.dumps(MANIFEST, ensure_ascii=False, indent=1), encoding='utf-8')

# --- теги PWA в index.html (в одиночный quiz.html они не идут)
html = (APP / 'index.html').read_text(encoding='utf-8')
# Та же рюмка, что на домашнем экране, идёт и во вкладку браузера — иначе
# в закладках и в списке вкладок приложение выглядит безымянным листом.
tags = ('<link rel="manifest" href="manifest.webmanifest">\n'
        '<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">\n'
        '<link rel="icon" type="image/png" sizes="512x512" href="icon-512.png">\n'
        '<link rel="apple-touch-icon" href="icon-192.png">\n'
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n'
        '<meta name="mobile-web-app-capable" content="yes">\n')
if 'manifest.webmanifest' not in html:
    html = html.replace('</head>', tags + '</head>', 1)
reg = ("<script>if('serviceWorker' in navigator && location.protocol==='https:')"
       "{addEventListener('load',()=>navigator.serviceWorker.register('sw.js')"
       ".catch(e=>console.warn('sw',e)));}</script>\n")
if 'serviceWorker' not in html:
    html = html.replace('</body>', reg + '</body>', 1)
(APP / 'index.html').write_text(html, encoding='utf-8')

# --- service worker с версией = хеш содержимого приложения
h = hashlib.sha1()
for f in FILES + ['icon-192.png', 'icon-512.png']:
    h.update((APP / f).read_bytes())
ver = h.hexdigest()[:8]
(APP / 'sw.js').write_text(f"""// собирается scripts/42_pwa.py — руками не править
const CACHE = 'barquiz-{ver}';
const FILES = {json.dumps(['./'] + FILES + ['icon-192.png', 'icon-512.png'])};
self.addEventListener('install', e => {{
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
}});
self.addEventListener('activate', e => {{
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
}});
// Интерфейс — сеть первым: иначе после выкатки телефон ещё один-два запуска показывает
// старую версию из кеша (мы на этом ловились с категорией сотрудника). Офлайн —
// откат в кеш, поэтому в баре без сети приложение всё равно открывается.
// Данные (bank.js, media.js, картинки) — кеш первым: они большие и меняются вместе с CACHE.
self.addEventListener('fetch', e => {{
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  const isShell = e.request.mode === 'navigate' ||
                  url.pathname.endsWith('/') || url.pathname.endsWith('index.html');
  if (isShell) {{
    e.respondWith(
      fetch(e.request)
        .then(r => {{ const copy = r.clone();
                     caches.open(CACHE).then(c => c.put(e.request, copy)); return r; }})
        .catch(() => caches.match(e.request).then(r => r || caches.match('./'))));
    return;
  }}
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
}});
""", encoding='utf-8')

print(f'PWA: манифест, иконки 192/512, sw.js (кеш barquiz-{ver})')
