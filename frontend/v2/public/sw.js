/**
 * PARWA Service Worker
 *
 * Handles caching strategies, offline support, and push notifications
 * for the PARWA AI Support PWA.
 *
 * @version 2.0.0
 */

// Configuration
const CACHE_VERSION = "v2.0.0";
const STATIC_CACHE_NAME = `parwa-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE_NAME = `parwa-dynamic-${CACHE_VERSION}`;
const API_CACHE_NAME = `parwa-api-${CACHE_VERSION}`;
const IMAGE_CACHE_NAME = `parwa-images-${CACHE_VERSION}`;

// Cache durations (in milliseconds)
const CACHE_DURATION = {
  STATIC: 30 * 24 * 60 * 60 * 1000, // 30 days
  API: 5 * 60 * 1000, // 5 minutes
  IMAGES: 7 * 24 * 60 * 60 * 1000, // 7 days
  DYNAMIC: 24 * 60 * 60 * 1000, // 24 hours
};

// Static assets to cache on install
const STATIC_ASSETS = [
  "/",
  "/dashboard",
  "/offline",
  "/manifest.json",
  "/favicon.ico",
  "/icons/icon-192x192.png",
  "/icons/icon-512x512.png",
];

// API routes with specific caching strategies
const API_ROUTES = {
  CACHE_FIRST: ["/api/analytics", "/api/settings"],
  NETWORK_FIRST: ["/api/tickets", "/api/approvals", "/api/dashboard"],
  NETWORK_ONLY: ["/api/auth", "/api/webhooks"],
  STALE_WHILE_REVALIDATE: ["/api/clients", "/api/users"],
};

/**
 * Determine caching strategy for a request.
 */
function getCacheStrategy(url) {
  const pathname = new URL(url).pathname;

  // Check for API routes
  for (const route of API_ROUTES.CACHE_FIRST) {
    if (pathname.startsWith(route)) return "cache-first";
  }
  for (const route of API_ROUTES.NETWORK_FIRST) {
    if (pathname.startsWith(route)) return "network-first";
  }
  for (const route of API_ROUTES.NETWORK_ONLY) {
    if (pathname.startsWith(route)) return "network-only";
  }
  for (const route of API_ROUTES.STALE_WHILE_REVALIDATE) {
    if (pathname.startsWith(route)) return "stale-while-revalidate";
  }

  // Default to network-first for API, cache-first for static
  return pathname.startsWith("/api") ? "network-first" : "cache-first";
}

/**
 * Install event - cache static assets.
 */
self.addEventListener("install", (event) => {
  console.log("[SW] Installing service worker...");

  event.waitUntil(
    caches.open(STATIC_CACHE_NAME).then((cache) => {
      console.log("[SW] Caching static assets");
      return cache.addAll(STATIC_ASSETS);
    })
  );

  // Activate immediately
  self.skipWaiting();
});

/**
 * Activate event - clean up old caches.
 */
self.addEventListener("activate", (event) => {
  console.log("[SW] Activating service worker...");

  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => {
            return (
              name.startsWith("parwa-") &&
              name !== STATIC_CACHE_NAME &&
              name !== DYNAMIC_CACHE_NAME &&
              name !== API_CACHE_NAME &&
              name !== IMAGE_CACHE_NAME
            );
          })
          .map((name) => {
            console.log("[SW] Deleting old cache:", name);
            return caches.delete(name);
          })
      );
    })
  );

  // Take control of all clients immediately
  self.clients.claim();
});

/**
 * Fetch event - handle requests with appropriate caching strategy.
 */
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests for caching
  if (request.method !== "GET") {
    // Queue non-GET requests for background sync
    if (request.url.includes("/api/")) {
      event.respondWith(handleNonGetRequest(request));
      return;
    }
    return;
  }

  // Skip cross-origin requests
  if (url.origin !== location.origin) {
    return;
  }

  const strategy = getCacheStrategy(request.url);

  switch (strategy) {
    case "cache-first":
      event.respondWith(cacheFirst(request));
      break;
    case "network-first":
      event.respondWith(networkFirst(request));
      break;
    case "network-only":
      event.respondWith(networkOnly(request));
      break;
    case "stale-while-revalidate":
      event.respondWith(staleWhileRevalidate(request));
      break;
    default:
      event.respondWith(cacheFirst(request));
  }
});

/**
 * Cache-first strategy.
 * Try cache first, fall back to network.
 */
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(request);
    const cache = await caches.open(STATIC_CACHE_NAME);
    cache.put(request, response.clone());
    return response;
  } catch (error) {
    return getOfflineFallback(request);
  }
}

/**
 * Network-first strategy.
 * Try network first, fall back to cache.
 */
async function networkFirst(request) {
  const cache = await caches.open(API_CACHE_NAME);

  try {
    const response = await fetch(request);

    // Only cache successful responses
    if (response.ok) {
      cache.put(request, response.clone());
    }

    return response;
  } catch (error) {
    // Try cache
    const cached = await cache.match(request);
    if (cached) {
      console.log("[SW] Serving from cache:", request.url);
      return cached;
    }

    return getOfflineFallback(request);
  }
}

/**
 * Network-only strategy.
 * Only use network, no caching.
 */
async function networkOnly(request) {
  try {
    return await fetch(request);
  } catch (error) {
    return new Response(JSON.stringify({ error: "Network unavailable" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

/**
 * Stale-while-revalidate strategy.
 * Return cache immediately, update in background.
 */
async function staleWhileRevalidate(request) {
  const cache = await caches.open(DYNAMIC_CACHE_NAME);
  const cached = await cache.match(request);

  // Start network fetch in background
  const networkPromise = fetch(request).then((response) => {
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  });

  // Return cached version or wait for network
  return cached || networkPromise;
}

/**
 * Get offline fallback response.
 */
async function getOfflineFallback(request) {
  const url = new URL(request.url);

  // Return offline page for navigation requests
  if (request.mode === "navigate") {
    const offlinePage = await caches.match("/offline");
    if (offlinePage) {
      return offlinePage;
    }
  }

  // Return error JSON for API requests
  if (url.pathname.startsWith("/api/")) {
    return new Response(
      JSON.stringify({
        error: "offline",
        message: "You are currently offline. Request has been queued for sync.",
        timestamp: new Date().toISOString(),
      }),
      {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }
    );
  }

  // Return placeholder for images
  if (request.destination === "image") {
    return new Response(
      '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect fill="#1e293b" width="100" height="100"/><text x="50" y="50" text-anchor="middle" fill="#94a3b8" font-size="12">Offline</text></svg>',
      { headers: { "Content-Type": "image/svg+xml" } }
    );
  }

  return new Response("Offline", { status: 503 });
}

/**
 * Handle non-GET requests when offline.
 */
async function handleNonGetRequest(request) {
  try {
    return await fetch(request);
  } catch (error) {
    // Queue request for background sync
    const requestData = {
      url: request.url,
      method: request.method,
      headers: Object.fromEntries(request.headers.entries()),
      body: await request.text(),
      timestamp: Date.now(),
    };

    // Store in IndexedDB for later sync
    await storePendingRequest(requestData);

    return new Response(
      JSON.stringify({
        success: false,
        message: "Request queued for background sync",
        offline: true,
      }),
      {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}

/**
 * Store pending request in IndexedDB.
 */
async function storePendingRequest(requestData) {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(["pendingRequests"], "readwrite");
    const store = transaction.objectStore("pendingRequests");
    const request = store.add(requestData);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Open IndexedDB database.
 */
function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("parwa-offline", 1);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains("pendingRequests")) {
        db.createObjectStore("pendingRequests", {
          keyPath: "id",
          autoIncrement: true,
        });
      }
    };
  });
}

/**
 * Background sync event.
 */
self.addEventListener("sync", (event) => {
  console.log("[SW] Background sync triggered:", event.tag);

  if (event.tag === "sync-pending-requests") {
    event.waitUntil(syncPendingRequests());
  }
});

/**
 * Sync pending requests.
 */
async function syncPendingRequests() {
  const db = await openDatabase();
  const transaction = db.transaction(["pendingRequests"], "readwrite");
  const store = transaction.objectStore("pendingRequests");

  const pendingRequests = await new Promise((resolve, reject) => {
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  console.log("[SW] Syncing pending requests:", pendingRequests.length);

  for (const requestData of pendingRequests) {
    try {
      const response = await fetch(requestData.url, {
        method: requestData.method,
        headers: requestData.headers,
        body: requestData.body,
      });

      if (response.ok) {
        // Remove from pending queue
        store.delete(requestData.id);
        console.log("[SW] Successfully synced request:", requestData.url);
      }
    } catch (error) {
      console.error("[SW] Failed to sync request:", requestData.url, error);
    }
  }

  // Notify clients about sync completion
  const clients = await self.clients.matchAll();
  clients.forEach((client) => {
    client.postMessage({
      type: "SYNC_COMPLETE",
      pendingCount: pendingRequests.length,
    });
  });
}

/**
 * Push notification event.
 */
self.addEventListener("push", (event) => {
  console.log("[SW] Push notification received");

  let data = {
    title: "PARWA Notification",
    body: "You have a new notification",
    icon: "/icons/icon-192x192.png",
    badge: "/icons/badge-72x72.png",
    tag: "general",
    data: {},
  };

  if (event.data) {
    try {
      data = { ...data, ...event.data.json() };
    } catch (error) {
      console.error("[SW] Failed to parse push data:", error);
    }
  }

  const options = {
    body: data.body,
    icon: data.icon,
    badge: data.badge,
    tag: data.tag,
    data: data.data,
    vibrate: [100, 50, 100],
    actions: data.actions || [
      { action: "view", title: "View" },
      { action: "dismiss", title: "Dismiss" },
    ],
    requireInteraction: data.requireInteraction || false,
    silent: data.silent || false,
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

/**
 * Notification click event.
 */
self.addEventListener("notificationclick", (event) => {
  console.log("[SW] Notification clicked:", event.action);

  event.notification.close();

  const action = event.action;
  const data = event.notification.data || {};

  if (action === "dismiss") {
    return;
  }

  // Open or focus the app
  const urlToOpen = data.url || "/dashboard";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      // Check if there's already a window open
      for (const client of clientList) {
        if (client.url.includes(urlToOpen) && "focus" in client) {
          client.postMessage({
            type: "NOTIFICATION_CLICK",
            data: data,
          });
          return client.focus();
        }
      }

      // Open new window
      if (self.clients.openWindow) {
        return self.clients.openWindow(urlToOpen);
      }
    })
  );
});

/**
 * Notification close event.
 */
self.addEventListener("notificationclose", (event) => {
  console.log("[SW] Notification closed");
});

/**
 * Message event - handle messages from main thread.
 */
self.addEventListener("message", (event) => {
  console.log("[SW] Message received:", event.data);

  if (event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }

  if (event.data.type === "CACHE_URLS") {
    event.waitUntil(
      caches.open(DYNAMIC_CACHE_NAME).then((cache) => {
        return cache.addAll(event.data.urls);
      })
    );
  }

  if (event.data.type === "CLEAR_CACHE") {
    event.waitUntil(
      caches.keys().then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name.startsWith("parwa-"))
            .map((name) => caches.delete(name))
        );
      })
    );
  }

  if (event.data.type === "GET_PENDING_COUNT") {
    getPendingRequestCount().then((count) => {
      event.ports[0]?.postMessage({ count });
    });
  }
});

/**
 * Get count of pending requests.
 */
async function getPendingRequestCount() {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(["pendingRequests"], "readonly");
    const store = transaction.objectStore("pendingRequests");
    const request = store.count();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

console.log("[SW] Service worker loaded");
