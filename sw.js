/* Service Worker: Seite und Daten immer zuerst frisch aus dem Netz. Rückfallebene: Ist das Netz weg oder antwortet der
   Server mit einem Fehler, kommt die zuletzt geladene Datei aus dem Speicher (markiert mit x-sd-cache, die Seite zeigt das an). */
const CACHE = 'sd-v1';   // Name bleibt, damit der gespeicherte Stand bei Updates erhalten bleibt
self.addEventListener('install', (e) => { self.skipWaiting(); });
self.addEventListener('activate', (e) => { e.waitUntil(self.clients.claim()); });
const fromCache = (key, fallback) => caches.open(CACHE).then((cache) => cache.match(key)).then((r) => {
  if (!r) return fallback || Response.error();
  const h = new Headers(r.headers); h.set('x-sd-cache', '1');
  return r.blob().then((b) => new Response(b, {status: 200, headers: h}));
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || (url.origin !== location.origin && !url.hostname.endsWith('cdnjs.cloudflare.com'))) return;
  const key = url.origin + url.pathname;                      // ?v=… (Cache-Buster) ignorieren
  e.respondWith(fetch(e.request).then((r) => {
    if (r.ok) { const c = r.clone(); caches.open(CACHE).then((cache) => cache.put(key, c)); return r; }
    return fromCache(key, r);                                 // Serverfehler: gespeicherten Stand nehmen, sonst Fehler weiterreichen
  }).catch(() => fromCache(key)));
});
