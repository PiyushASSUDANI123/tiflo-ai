// ── Tiflo AI Service Worker ──────────────────────────────────────────────────
// Owner: Piyush Assudani | Assudani Group | tiflo.in
// Handles offline caching, background sync and PWA install.

const CACHE_NAME = 'tiflo-ai-v4'; // bumped for v1.0.1 release
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/image.png',
    '/manifest.json',
    '/terms.html',
    '/privacy.html'
];

// ── Install: Pre-cache shell assets ──────────────────────────────────────────
self.addEventListener('install', (event) => {
    console.log('[Tiflo SW] Installing Service Worker...');
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Tiflo SW] Caching static shell assets');
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// ── Activate: Clean old caches ────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
    console.log('[Tiflo SW] Activating Service Worker...');
    event.waitUntil(
        caches.keys().then((cacheNames) =>
            Promise.all(
                cacheNames
                    .filter((name) => name !== CACHE_NAME)
                    .map((name) => {
                        console.log('[Tiflo SW] Deleting old cache:', name);
                        return caches.delete(name);
                    })
            )
        )
    );
    self.clients.claim();
});

// ── Fetch: Network-first for API, Cache-first for static ─────────────────────
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // API calls — always go network-first, never cache
    if (
        url.hostname.includes('localhost') ||
        url.hostname.includes('hf.space') ||
        url.hostname.includes('openrouter.ai') ||
        url.hostname.includes('firebaseio.com') ||
        url.pathname.startsWith('/chat') ||
        url.pathname.startsWith('/memory') ||
        url.pathname.startsWith('/health')
    ) {
        event.respondWith(fetch(event.request));
        return;
    }

    // Static shell assets — cache-first with network fallback
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) return cachedResponse;

            return fetch(event.request)
                .then((networkResponse) => {
                    // Cache successful GET responses for static files
                    if (
                        networkResponse.ok &&
                        event.request.method === 'GET' &&
                        !url.pathname.includes('mixpanel')
                    ) {
                        const responseClone = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return networkResponse;
                })
                .catch(() => {
                    // Offline fallback — serve index.html
                    return caches.match('/index.html');
                });
        })
    );
});

// ── Push Notifications (future use) ──────────────────────────────────────────
self.addEventListener('push', (event) => {
    const data = event.data?.json() ?? { title: 'Tiflo AI', body: 'New message!' };
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/image.png',
            badge: '/image.png',
            vibrate: [100, 50, 100]
        })
    );
});

// ── Skip Waiting message listener ───────────────────────────────────────────
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
