const VERSION = 'v1.5.0';  // Fixed version that works

// Install immediately
self.addEventListener('install', (e) => {
    console.log('[SW] Installing v1.5.0...');
    e.waitUntil(self.skipWaiting());
});

// Activate immediately  
self.addEventListener('activate', (e) => {
    console.log('[SW] Activating v1.5.0...');
    e.waitUntil(
        caches.keys().then(names => 
            Promise.all(names.map(name => name !== VERSION ? caches.delete(name) : null))
        ).then(() => self.clients.claim())
    );
});

// Bypass API calls completely
const isAPI = (url) => 
    url.pathname.startsWith('/ai-chat') || 
    url.pathname.startsWith('/api/');

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // NEVER intercept API calls - let browser handle directly
    if (isAPI(url)) {
        console.log('[SW] Bypassing API call:', url.pathname);
        return;
    }
    
    // Network-first for HTML documents (chat, report pages)  
    if (event.request.destination === 'document') {
        event.respondWith(
            fetch(event.request, { cache: 'no-store' })
                .then(response => {
                    console.log('[SW] Fresh HTML served:', url.pathname);
                    return response;
                })
                .catch(() => {
                    console.log('[SW] HTML fetch failed, trying cache:', url.pathname);
                    return caches.match(event.request) || 
                           new Response('Offline', { status: 503 });
                })
        );
        return;
    }
    
    // Cache-first for static assets with error handling
    if (event.request.method === 'GET' && 
        /\.(css|js|png|jpg|svg|woff2?|ico)$/.test(url.pathname)) {
        
        event.respondWith(
            caches.open(VERSION)
                .then(cache => cache.match(event.request))
                .then(cachedResponse => {
                    if (cachedResponse) {
                        console.log('[SW] Serving from cache:', url.pathname);
                        return cachedResponse;
                    }
                    
                    return fetch(event.request)
                        .then(response => {
                            if (response.ok) {
                                const responseClone = response.clone();
                                caches.open(VERSION)
                                    .then(cache => cache.put(event.request, responseClone))
                                    .catch(err => console.warn('[SW] Cache failed for:', url.pathname, err));
                            }
                            return response;
                        });
                })
                .catch(err => {
                    console.error('[SW] Asset fetch failed:', url.pathname, err);
                    return new Response('Asset unavailable', { status: 503 });
                })
        );
    }
});