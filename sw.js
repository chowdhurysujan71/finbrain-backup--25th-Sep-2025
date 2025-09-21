// finbrain PWA Service Worker
// Handles caching, offline functionality, and background sync

const CACHE_NAME = 'finbrain-v1.1.1-auth-fix';
const STATIC_CACHE_NAME = 'finbrain-static-v1.1.1-auth-fix';
const API_CACHE_NAME = 'finbrain-api-v1.1.1-auth-fix';

// Resources to precache on install - SECURITY: Only static assets, never HTML
const PRECACHE_URLS = [
    '/manifest.webmanifest',
    '/static/css/app.css',
    '/static/js/pwa.js',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png'
];

// SECURITY: Restricted HTML paths that must never be cached
const RESTRICTED_HTML_PATHS = ['/', '/chat', '/report', '/profile', '/challenge', '/login', '/register'];

// Current cache names for legacy purge
const CURRENT_CACHE_NAMES = new Set([CACHE_NAME, STATIC_CACHE_NAME, API_CACHE_NAME]);

// BroadcastChannel for client coordination
const swControlChannel = new BroadcastChannel('sw-control');

// Aggressive legacy cache purge - SECURITY CRITICAL
async function purgeLegacyCaches() {
    try {
        console.log('[SW] Starting aggressive legacy cache purge...');
        
        // Step 1: Delete all caches not in current version
        const cacheNames = await caches.keys();
        const deletionPromises = [];
        
        for (const cacheName of cacheNames) {
            if (!CURRENT_CACHE_NAMES.has(cacheName)) {
                console.log('[SW] PURGING legacy cache:', cacheName);
                deletionPromises.push(caches.delete(cacheName));
            }
        }
        
        await Promise.all(deletionPromises);
        
        // Step 2: Purge any HTML entries from remaining caches
        const remainingCaches = await caches.keys();
        for (const cacheName of remainingCaches) {
            const cache = await caches.open(cacheName);
            const requests = await cache.keys();
            
            for (const request of requests) {
                const url = new URL(request.url);
                
                // Delete if it's a restricted HTML path or document type
                if (RESTRICTED_HTML_PATHS.includes(url.pathname) || 
                    request.destination === 'document') {
                    console.log('[SW] PURGING HTML entry:', url.pathname, 'from', cacheName);
                    await cache.delete(request);
                }
            }
        }
        
        console.log('[SW] Legacy cache purge completed successfully');
    } catch (error) {
        console.error('[SW] Legacy cache purge failed:', error);
        // Don't fail installation/activation on purge failure
    }
}

// Install event - precache critical resources
self.addEventListener('install', event => {
    console.log('[SW] Installing service worker v1.1.1...');
    
    event.waitUntil(
        Promise.all([
            // Aggressive legacy purge first
            purgeLegacyCaches(),
            
            // Then precache static resources
            caches.open(STATIC_CACHE_NAME)
                .then(cache => {
                    console.log('[SW] Precaching static resources');
                    // Cache resources one by one, skip failures
                    return Promise.allSettled(
                        PRECACHE_URLS.map(url => 
                            cache.add(url).catch(error => {
                                console.warn('[SW] Failed to cache:', url, error);
                                return null;
                            })
                        )
                    );
                })
        ]).then(() => {
            console.log('[SW] Skip waiting to activate immediately');
            return self.skipWaiting();
        }).catch(error => {
            console.error('[SW] Install failed:', error);
            // Don't fail installation if precaching fails
            return self.skipWaiting();
        })
    );
});

// Activate event - clean up old caches and claim clients
self.addEventListener('activate', event => {
    console.log('[SW] Activating service worker v1.1.1...');
    
    event.waitUntil(
        Promise.all([
            // Aggressive legacy purge on activation
            purgeLegacyCaches(),
            
            // Take control of all clients immediately
            self.clients.claim()
        ]).then(() => {
            console.log('[SW] Service worker v1.1.1 activated and ready');
            
            // Notify clients that new SW is ready
            swControlChannel.postMessage({
                type: 'SW_READY',
                version: 'v1.1.1-auth-fix',
                timestamp: Date.now()
            });
        })
    );
});

// Counter for first-fetch purges
let fetchCounter = 0;

// Fetch event - handle all network requests with caching strategies
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Run legacy purge on first 3 fetches for belt-and-suspenders cleanup
    if (fetchCounter < 3) {
        fetchCounter++;
        purgeLegacyCaches().catch(err => console.warn('[SW] Fetch purge failed:', err));
    }
    
    // Never cache API calls; always go network
    if (url.pathname.startsWith('/api/')) {
        return; // bypass SW completely for all API requests
    }
    
    // Skip non-GET requests and chrome-extension requests
    if (request.method !== 'GET' || url.protocol === 'chrome-extension:') {
        return;
    }
    
    // Different strategies based on request type
    if (isNavigationRequest(request)) {
        // Navigation requests - network first with offline fallback
        event.respondWith(handleNavigationRequest(request));
    } else if (isStaticAsset(request)) {
        // Static assets - cache first
        event.respondWith(handleStaticAsset(request));
    } else if (isAPIRequest(request)) {
        // API requests - network first with cache fallback
        event.respondWith(handleAPIRequest(request));
    } else {
        // Default - network first
        event.respondWith(handleDefaultRequest(request));
    }
});

// Handle navigation requests (HTML pages) - SECURITY: Never cache HTML
async function handleNavigationRequest(request) {
    try {
        // Always try network first - never cache HTML responses
        const networkResponse = await fetch(request);
        
        // SECURITY FIX: Do NOT cache any HTML responses
        // Return response directly without caching
        return networkResponse;
    } catch (error) {
        console.log('[SW] Navigation request failed, serving synthesized offline page:', error);
        
        // SECURITY FIX: Synthesize offline response instead of caching HTML
        return new Response(`
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>FinBrain - Offline</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
                           text-align: center; padding: 2rem; background: #f8f9fa; }
                    .offline-icon { font-size: 4rem; margin: 2rem 0; }
                    h1 { color: #495057; margin: 1rem 0; }
                    p { color: #6c757d; max-width: 400px; margin: 0 auto 2rem; }
                    button { background: #007bff; color: white; border: none; padding: 0.5rem 1rem; 
                             border-radius: 4px; cursor: pointer; }
                    button:hover { background: #0056b3; }
                </style>
            </head>
            <body>
                <div class="offline-icon">📱</div>
                <h1>You're Offline</h1>
                <p>FinBrain needs an internet connection to work properly. Please check your connection and try again.</p>
                <button onclick="location.reload()">Try Again</button>
            </body>
            </html>
        `, {
            status: 200,
            statusText: 'OK',
            headers: {
                'Content-Type': 'text/html; charset=utf-8',
                'Cache-Control': 'no-cache, no-store, must-revalidate'
            }
        });
    }
}

// Handle static assets (CSS, JS, images, icons)
async function handleStaticAsset(request) {
    try {
        // Try cache first
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // Fallback to network
        const networkResponse = await fetch(request);
        
        // Cache the response
        if (networkResponse.ok) {
            const cache = await caches.open(STATIC_CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[SW] Static asset request failed:', error);
        
        // For icons, try to serve a default if available
        if (request.url.includes('/icons/')) {
            return caches.match('/static/icons/icon-192.png');
        }
        
        throw error;
    }
}

// Handle API requests
async function handleAPIRequest(request) {
    try {
        // Try network first
        const networkResponse = await fetch(request);
        
        // Cache successful GET responses
        if (networkResponse.ok && request.method === 'GET') {
            const cache = await caches.open(API_CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[SW] API request failed, checking cache:', error);
        
        // Try to serve from cache for GET requests
        if (request.method === 'GET') {
            const cachedResponse = await caches.match(request);
            if (cachedResponse) {
                return cachedResponse;
            }
        }
        
        // Return a friendly offline response for failed API calls
        return new Response(
            JSON.stringify({
                error: 'Offline',
                message: 'This feature requires an internet connection'
            }),
            {
                status: 503,
                statusText: 'Service Unavailable',
                headers: { 'Content-Type': 'application/json' }
            }
        );
    }
}

// Handle other requests - SECURITY: Never cache HTML
async function handleDefaultRequest(request) {
    try {
        const networkResponse = await fetch(request);
        
        // Check if response is HTML and skip caching if so
        const contentType = networkResponse.headers.get('content-type') || '';
        const isHTML = contentType.includes('text/html');
        
        // Cache successful responses (except HTML)
        if (networkResponse.ok && !isHTML) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[SW] Default request failed, checking cache:', error);
        
        // Only serve cached non-HTML responses
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            const contentType = cachedResponse.headers.get('content-type') || '';
            if (!contentType.includes('text/html')) {
                return cachedResponse;
            }
        }
        
        throw error;
    }
}

// Helper functions
function isNavigationRequest(request) {
    return request.mode === 'navigate' || 
           (request.method === 'GET' && request.headers.get('accept').includes('text/html'));
}

function isStaticAsset(request) {
    const url = new URL(request.url);
    return url.pathname.startsWith('/static/') ||
           url.pathname.includes('.css') ||
           url.pathname.includes('.js') ||
           url.pathname.includes('.png') ||
           url.pathname.includes('.jpg') ||
           url.pathname.includes('.ico') ||
           url.pathname.includes('.svg');
}

function isAPIRequest(request) {
    const url = new URL(request.url);
    return url.pathname.startsWith('/api/') ||
           url.pathname.startsWith('/webhook/') ||
           url.pathname.startsWith('/partials/') ||
           url.pathname.includes('/expense') ||
           url.pathname.includes('/health');
}

// Background sync for offline actions (future enhancement)
self.addEventListener('sync', event => {
    console.log('[SW] Background sync event:', event.tag);
    
    if (event.tag === 'expense-sync') {
        event.waitUntil(syncExpenses());
    }
});

// Sync offline expenses when back online
async function syncExpenses() {
    try {
        console.log('[SW] Syncing offline expenses...');
        
        // Get offline expenses from IndexedDB (to be implemented)
        // const offlineExpenses = await getOfflineExpenses();
        
        // Send each expense to server
        // for (const expense of offlineExpenses) {
        //     await fetch('/expense', {
        //         method: 'POST',
        //         headers: { 'Content-Type': 'application/json' },
        //         body: JSON.stringify(expense)
        //     });
        // }
        
        console.log('[SW] Expense sync completed');
    } catch (error) {
        console.error('[SW] Expense sync failed:', error);
        throw error;
    }
}

// Push notification handling (future enhancement)
self.addEventListener('push', event => {
    console.log('[SW] Push notification received');
    
    const options = {
        body: 'You have new financial insights available!',
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/icon-192.png',
        vibrate: [100, 50, 100],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1
        },
        actions: [
            {
                action: 'explore',
                title: 'View insights',
                icon: '/static/icons/icon-192.png'
            },
            {
                action: 'close',
                title: 'Close',
                icon: '/static/icons/icon-192.png'
            }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification('FinBrain', options)
    );
});

// Notification click handling
self.addEventListener('notificationclick', event => {
    console.log('[SW] Notification click received');
    
    event.notification.close();
    
    if (event.action === 'explore') {
        event.waitUntil(
            clients.openWindow('/report')
        );
    }
});

// Message handling for communication with main thread
self.addEventListener('message', event => {
    console.log('[SW] Message received:', event.data);
    
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data && event.data.type === 'GET_VERSION') {
        event.ports[0].postMessage({
            version: CACHE_NAME
        });
    }
});

console.log('[SW] Service worker script loaded');