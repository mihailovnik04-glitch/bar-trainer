// собирается scripts/42_pwa.py — руками не править
const CACHE = 'barquiz-b0e3e9ea';
const FILES = ["./", "index.html", "bank.js", "recipes.js", "media.js", "manifest.webmanifest", "icon-192.png", "icon-512.png"];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
// Интерфейс — сеть первым: иначе после выкатки телефон ещё один-два запуска показывает
// старую версию из кеша (мы на этом ловились с категорией сотрудника). Офлайн —
// откат в кеш, поэтому в баре без сети приложение всё равно открывается.
// Данные (bank.js, media.js, картинки) — кеш первым: они большие и меняются вместе с CACHE.
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  const isShell = e.request.mode === 'navigate' ||
                  url.pathname.endsWith('/') || url.pathname.endsWith('index.html');
  if (isShell) {
    e.respondWith(
      fetch(e.request)
        .then(r => { const copy = r.clone();
                     caches.open(CACHE).then(c => c.put(e.request, copy)); return r; })
        .catch(() => caches.match(e.request).then(r => r || caches.match('./'))));
    return;
  }
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
