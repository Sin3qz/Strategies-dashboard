/* Service Worker: Seite und Daten immer zuerst frisch aus dem Netz, bei Funkloch der zuletzt geladene Stand. */
const CACHE = 'sd-v1';
self.addEventListener('install', (e) => { self.skipWaiting(); });
self.addEventListener('activate', (e) => { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || (url.origin !== location.origin && !url.hostname.endsWith('cdnjs.cloudflare.com'))) return;
  const key = url.origin + url.pathname;                      // ?v=… (Cache-Buster) ignorieren
  e.respondWith(fetch(e.request).then((r) => {
    if (r.ok) { const c = r.clone(); caches.open(CACHE).then((cache) => cache.put(key, c)); }
    return r;
  }).catch(() => caches.open(CACHE).then((cache) => cache.match(key)).then((r) => r || Response.error())));
});
