// CACHE DESTROYER - ULTRA AGGRESSIVE CACHE BUSTING
console.error('🚀 [CACHE-DESTROYER] Loading ultra-aggressive cache buster...');

// Check if we're on stale cache
const currentTime = Date.now();
const lastCacheBust = localStorage.getItem('finbrain_cache_bust');
const buildVersion = '2025-09-18-ULTRA';

// Store build info
localStorage.setItem('finbrain_build_version', buildVersion);
localStorage.setItem('finbrain_cache_bust', currentTime.toString());

// Check if we need to force reload
const needsReload = !lastCacheBust || 
                  (currentTime - parseInt(lastCacheBust)) > (1000 * 60 * 5) || // 5 min force
                  localStorage.getItem('finbrain_build_version') !== buildVersion;

if (needsReload) {
    console.error('🚨 [CACHE-DESTROYER] FORCING NUCLEAR RELOAD...');
    
    // Nuclear option: Clear everything
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.getRegistrations()
            .then(registrations => {
                const unregPromises = registrations.map(reg => reg.unregister());
                return Promise.all(unregPromises);
            })
            .then(() => {
                // Clear all caches
                if ('caches' in window) {
                    caches.keys().then(cacheNames => {
                        return Promise.all(cacheNames.map(cacheName => caches.delete(cacheName)));
                    });
                }
                
                // Force reload with cache bypass
                setTimeout(() => {
                    window.location.reload(true);
                }, 100);
            });
    } else {
        // Fallback for browsers without SW support
        window.location.reload(true);
    }
}

console.error('🚀 [CACHE-DESTROYER] Build version:', buildVersion);