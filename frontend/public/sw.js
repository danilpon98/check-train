/* trainwatch service worker: показывает Web Push уведомления, даже когда вкладка закрыта. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('push', (event) => {
  let p = {};
  try { p = event.data ? event.data.json() : {}; } catch (_) { p = { title: 'trainwatch', body: event.data && event.data.text() }; }
  const alert = p.kind === 'alert';
  const opts = {
    body: p.body || '',
    tag: p.tag || 'trainwatch',
    renotify: true,
    icon: '/static/icon-192.png',
    badge: '/static/badge-96.png',
    requireInteraction: !!p.requireInteraction,
    silent: false,
    vibrate: alert ? [400, 150, 400, 150, 800] : [150],
    timestamp: Date.now(),
    data: { url: p.url || null, kind: p.kind, eventId: p.event_id || null },
    actions: p.url ? [
      { action: 'buy', title: alert ? '🎫 Купить на сайте' : 'Открыть сайт' },
      { action: 'open', title: 'Открыть trainwatch' },
    ] : [],
  };
  event.waitUntil((async () => {
    await self.registration.showNotification(p.title || 'trainwatch', opts);
    const tabs = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    tabs.forEach((c) => c.postMessage({ type: 'push', payload: p }));
  })());
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const data = event.notification.data || {};
  event.waitUntil((async () => {
    if (event.action === 'buy' && data.url) return self.clients.openWindow(data.url);
    const tabs = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const own = tabs.find((c) => new URL(c.url).origin === self.location.origin);
    if (own) { await own.focus(); own.postMessage({ type: 'focus-event', eventId: data.eventId }); return; }
    return self.clients.openWindow('/');
  })());
});

// Браузер может сменить подписку — переподписываемся и сообщаем серверу.
self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil((async () => {
    const st = await (await fetch('/api/state', { credentials: 'include' })).json();
    const key = st.push && st.push.public_key;
    if (!key) return;
    const pad = '='.repeat((4 - key.length % 4) % 4);
    const raw = atob((key + pad).replace(/-/g, '+').replace(/_/g, '/'));
    const sub = await self.registration.pushManager.subscribe({
      userVisibleOnly: true, applicationServerKey: Uint8Array.from(raw, (c) => c.charCodeAt(0)),
    });
    await fetch('/api/push/subscribe', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subscription: sub.toJSON() }),
    });
  })());
});
