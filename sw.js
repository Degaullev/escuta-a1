/**
 * Escuta A1 — PWA Service Worker
 * - Network-first with offline fallback for HTML, JS, CSS, and lesson JSON
 * - Bypasses HTTP Range requests so iOS Safari <video>/<audio> streaming never breaks
 */
const CACHE_NAME = "escuta-a1-pwa-v6";
const PROTECTED_USER_CACHE = "escuta-a1-user-data-permanent";
const CORE_ASSETS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./css/styles.css?v=11",
  "./js/srs-storage.js?v=11",
  "./js/audio-player.js?v=11",
  "./js/recorder.js?v=11",
  "./js/app.js?v=11",
  "./lessons/index.json",
  "./lessons/glossary.json",
  "./lessons/manaus-demo/lesson.json",
  "./icons/icon-192.png",
  "./icons/apple-touch-icon.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== CACHE_NAME && k !== PROTECTED_USER_CACHE)
            .map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  // Let iOS Safari handle byte-range media streaming natively
  if (req.headers.has("range")) return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.includes("/api/")) return;
  if (url.pathname.includes("__escuta_permanent_user_state__")) return;

  // Network-first for HTML & JSON so newly pushed lessons appear immediately
  if (
    req.mode === "navigate" ||
    url.pathname.endsWith(".json") ||
    url.pathname.endsWith(".js") ||
    url.pathname.endsWith(".css")
  ) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Cache-first for images, icons, and short chunk MP3s
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        if (res && res.status === 200) {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(req, copy));
        }
        return res;
      });
    })
  );
});
