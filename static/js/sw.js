const VERSION = 'v1.5.0';  

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

// Never intercept API calls
const isAPI = (url) => 
    url.pathname.startsWith('/ai-chat') || 
    url.pathname.startsWith('/api/');

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // NEVER intercept API calls - let browser handle directly
    if (isAPI(url)) {
        return;
    }
    
    // Network-first for HTML documents
    if (event.request.destination === 'document') {
        event.respondWith(
            fetch(event.request, { cache: 'no-store' })
                .then(response => response)
                .catch(() => caches.match(event.request) || 
                       new Response('Offline', { status: 503 }))
        );
        return;
    }
    
    // Cache-first for static assets
    if (event.request.method === 'GET' && 
        /\.(css|js|png|jpg|svg|woff2?|ico)$/.test(url.pathname)) {
        
        event.respondWith(
            caches.open(VERSION)
                .then(cache => cache.match(event.request))
                .then(cachedResponse => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    
                    return fetch(event.request)
                        .then(response => {
                            if (response.ok) {
                                const responseClone = response.clone();
                                caches.open(VERSION)
                                    .then(cache => cache.put(event.request, responseClone))
                                    .catch(() => {}); // Silent fail on cache errors
                            }
                            return response;
                        });
                })
        );
    }
});