const VERSION = 'v10';               // bump
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

const isAPI = (u) => u.pathname.startsWith('/ai-chat') || u.pathname.startsWith('/api/');

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (isAPI(url)) return; // let browser hit network; no SW caching

  // network-first for HTML to prevent stale pages (/chat, /report)
  if (event.request.destination === 'document') {
    event.respondWith((async () => {
      try { return await fetch(event.request, { cache: 'no-store' }); }
      catch { return await caches.match(event.request) || new Response('Offline', { status: 503 }); }
    })());
    return;
  }

  // cache-first for static assets
  if (event.request.method === 'GET' && /\.(css|js|png|jpg|svg|woff2?)$/.test(url.pathname)) {
    event.respondWith(caches.open(VERSION).then(async (cache) => {
      const hit = await cache.match(event.request);
      if (hit) return hit;
      const res = await fetch(event.request);
      cache.put(event.request, res.clone());
      return res;
    }));
  }
});