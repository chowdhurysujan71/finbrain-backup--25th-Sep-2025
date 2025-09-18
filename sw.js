// finbrain PWA Service Worker
// Handles caching, offline functionality, and background sync

const CACHE_NAME = 'finbrain-v1.0.0';
const STATIC_CACHE_NAME = 'finbrain-static-v1.0.0';
const API_CACHE_NAME = 'finbrain-api-v1.0.0';

// Resources to precache on install
const PRECACHE_URLS = [
    '/',
    '/chat',
    '/report', 
    '/profile',
    '/challenge',
    '/offline',
    '/manifest.webmanifest',
    '/static/css/app.css',
    '/static/js/pwa.js',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png'
];

// Install event - precache critical resources
self.addEventListener('install', event => {
    console.log('[SW] Installing service worker...');
    
    event.waitUntil(
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
            .then(() => {
                console.log('[SW] Skip waiting to activate immediately');
                return self.skipWaiting();
            })
            .catch(error => {
                console.error('[SW] Precache failed:', error);
                // Don't fail installation if precaching fails
                return self.skipWaiting();
            })
    );
});

// Activate event - clean up old caches and claim clients
self.addEventListener('activate', event => {
    console.log('[SW] Activating service worker...');
    
    event.waitUntil(
        Promise.all([
            // Clean up old caches
            caches.keys().then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (cacheName !== STATIC_CACHE_NAME && 
                            cacheName !== API_CACHE_NAME &&
                            cacheName !== CACHE_NAME) {
                            console.log('[SW] Deleting old cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            }),
            // Take control of all clients immediately
            self.clients.claim()
        ]).then(() => {
            console.log('[SW] Service worker activated and ready');
        })
    );
});

// Fetch event - handle all network requests with caching strategies
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
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

// Handle navigation requests (HTML pages)
async function handleNavigationRequest(request) {
    try {
        // Try network first
        const networkResponse = await fetch(request);
        
        // Cache successful responses
        if (networkResponse.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[SW] Navigation request failed, serving offline page:', error);
        
        // Try to serve from cache
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // Serve offline page
        return caches.match('/offline');
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

// Handle other requests
async function handleDefaultRequest(request) {
    try {
        const networkResponse = await fetch(request);
        
        // Cache successful responses
        if (networkResponse.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[SW] Default request failed, checking cache:', error);
        
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
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