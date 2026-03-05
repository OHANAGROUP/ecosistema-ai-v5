// ECOSISTEMA V5.0 — Service Worker (minimal stub)
// Prevents 404 on /sw.js and enables future PWA caching.

const CACHE_NAME = 'alpa-saas-v1';

self.addEventListener('install', (e) => {
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(clients.claim());
});

// No fetch interception — pass through all requests to network.
self.addEventListener('fetch', (e) => {
    e.respondWith(fetch(e.request).catch(() => new Response('Offline', { status: 503 })));
});
