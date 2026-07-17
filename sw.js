/* ================================================
   MO - Everything For You | SERVICE WORKER
   ================================================ */

const CACHE_NAME = 'mo-v2';
const STATIC_CACHE = 'mo-static-v2';
const DYNAMIC_CACHE = 'mo-dynamic-v2';

// NOTE: paths are relative to this file's own location (the site root),
// so the service worker keeps working when the app isn't hosted at a
// domain root (e.g. a GitHub Pages project page or any sub-path).
const STATIC_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './css/style.css',
  './css/live.css',
  './css/animations.css',
  './js/data-loader.js',
  './js/app.js',
  './js/player.js',
  './js/favorites.js',
  'https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&family=Inter:wght@300;400;500;600;700;800&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css',
  'https://cdn.jsdelivr.net/npm/hls.js@1.5.17/dist/hls.min.js',
  'https://cdn.jsdelivr.net/npm/mpegts.js@1.7.3/dist/mpegts.js'
];

// Large JSON catalogs are intentionally NOT precached here (multi-MB files
// would slow down / risk failing the install step). They're cached
// opportunistically by the same-origin fetch handler below on first use.

// Install event - cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('[SW] Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        console.log('[SW] Static assets cached');
        return self.skipWaiting();
      })
  );
});

// Activate event - clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
              console.log('[SW] Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('[SW] Activation complete');
        return self.clients.claim();
      })
  );
});

// Fetch event - serve from cache with network fallback
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip cross-origin requests for streaming
  if (url.origin !== self.location.origin) {
    // For streaming URLs, try network first
    if (url.pathname.includes('.m3u8') || url.pathname.includes('.ts') || url.hostname.includes('vidsrc')) {
      event.respondWith(
        fetch(event.request)
          .catch(() => {
            // Return error if network fails for streaming
            return new Response('Network error', { status: 503 });
          })
      );
      return;
    }
    
    // For other external resources, use network-first
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Cache successful responses
          if (response.ok) {
            const responseClone = response.clone();
            caches.open(DYNAMIC_CACHE).then((cache) => {
              cache.put(event.request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          // Try cache if network fails
          return caches.match(event.request);
        })
    );
    return;
  }

  // For same-origin requests, use cache-first strategy
  event.respondWith(
    caches.match(event.request)
      .then((cachedResponse) => {
        if (cachedResponse) {
          // Return cached version
          return cachedResponse;
        }

        // Not in cache, fetch from network
        return fetch(event.request)
          .then((networkResponse) => {
            // Cache the new response
            if (networkResponse.ok) {
              const responseClone = networkResponse.clone();
              caches.open(DYNAMIC_CACHE).then((cache) => {
                cache.put(event.request, responseClone);
              });
            }
            return networkResponse;
          })
          .catch(() => {
            // Return offline page for HTML requests
            if (event.request.headers.get('accept')?.includes('text/html')) {
              return caches.match('./index.html');
            }
          });
      })
  );
});

// Background sync for offline actions
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-favorites') {
    event.waitUntil(syncFavorites());
  }
  if (event.tag === 'sync-playlist') {
    event.waitUntil(syncPlaylist());
  }
});

// Push notifications
self.addEventListener('push', (event) => {
  const options = {
    body: event.data ? event.data.text() : 'إشعار جديد من MO',
    icon: './assets/icons/icon-192x192.png',
    badge: './assets/icons/icon-192x192.png',
    vibrate: [200, 100, 200],
    data: {
      url: '/'
    }
  };

  event.waitUntil(
    self.registration.showNotification('MO - Everything For You', options)
  );
});

// Notification click
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data.url || '/')
  );
});

// Helper functions
async function syncFavorites() {
  // Sync favorites with server if needed
  console.log('[SW] Syncing favorites');
}

async function syncPlaylist() {
  // Sync playlist with server if needed
  console.log('[SW] Syncing playlist');
}
