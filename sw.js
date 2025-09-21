// Minimal Service Worker: one-time cache purge, no runtime caching
// Version: v1.1.2-minimal-clean

self.addEventListener('install', (event) => {
  // Activate immediately
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // Delete ALL existing caches, then take control
  event.waitUntil((async () => {
    try {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    } catch (e) {
      // ignore
    }
    await self.clients.claim();
  })());
});

// IMPORTANT: no 'fetch' handler -> this SW never caches anything