import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/api/endpoints'
import { useAppStore } from './app'
import { useToastStore } from './toast'

export type PushState = 'on' | 'off' | 'denied' | 'insecure' | 'unsupported'

export function b64urlToBytes(s: string): Uint8Array<ArrayBuffer> {
  const pad = '='.repeat((4 - (s.length % 4)) % 4)
  const raw = atob((s + pad).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

export function bytesToB64url(buf: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/**
 * Web Push: регистрация Service Worker и подписка этого браузера.
 * Работает только в «безопасном контексте» — http://localhost или HTTPS.
 */
export const usePushStore = defineStore('push', () => {
  const registration = ref<ServiceWorkerRegistration | null>(null)
  const subscription = ref<PushSubscription | null>(null)
  const permission = ref<NotificationPermission | 'unsupported'>(
    typeof Notification === 'undefined' ? 'unsupported' : Notification.permission,
  )
  const busy = ref(false)

  const supported = typeof navigator !== 'undefined' && 'serviceWorker' in navigator
    && typeof window !== 'undefined' && 'PushManager' in window && typeof Notification !== 'undefined'

  const state = computed<PushState>(() => {
    if (typeof window !== 'undefined' && !window.isSecureContext) return 'insecure'
    if (!supported) return 'unsupported'
    if (permission.value === 'denied') return 'denied'
    return subscription.value ? 'on' : 'off'
  })

  async function init() {
    if (!supported || !window.isSecureContext) return
    try {
      registration.value = await navigator.serviceWorker.register('/sw.js', { scope: '/' })
      await navigator.serviceWorker.ready
      subscription.value = await registration.value.pushManager.getSubscription()
    } catch (e) {
      console.warn('service worker', e)
    }
  }

  /** Сервер мог потерять подписку (новая база) или сменить VAPID-ключ — приводим в соответствие. */
  async function sync() {
    const key = useAppStore().push?.public_key
    const sub = subscription.value
    if (!sub || !key) return
    const current = sub.options?.applicationServerKey
    if (current && bytesToB64url(current) !== key) {
      await sub.unsubscribe().catch(() => {})
      subscription.value = null
      await enable(true)
      return
    }
    await api.pushSubscribe(sub.toJSON()).catch(() => {})
  }

  async function enable(silent = false): Promise<boolean> {
    const toast = useToastStore()
    const app = useAppStore()
    if (state.value === 'insecure') { toast.show('Push работает только на http://localhost или по HTTPS'); return false }
    if (state.value === 'unsupported') { toast.show('Этот браузер не поддерживает Web Push'); return false }
    const key = app.push?.public_key
    if (!key) { toast.show('Сервер ещё не готов, попробуйте через секунду'); return false }
    busy.value = true
    try {
      if (!registration.value) await init()
      if (!registration.value) throw new Error('Service Worker не зарегистрирован')
      permission.value = await Notification.requestPermission()
      if (permission.value !== 'granted') {
        if (!silent) toast.show('Уведомления запрещены. Разрешите их для этого сайта в настройках браузера.', { ms: 6000 })
        return false
      }
      subscription.value = await registration.value.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: b64urlToBytes(key),
      })
      await api.pushSubscribe(subscription.value.toJSON())
      if (!silent) toast.show('Push-уведомления включены ✓')
      return true
    } catch (e) {
      toast.error(`Не удалось включить push: ${e instanceof Error ? e.message : e}. В Brave включите «Google services for push messaging».`, 8000)
      return false
    } finally {
      busy.value = false
      await app.refresh()
    }
  }

  async function disable() {
    const sub = subscription.value
    if (!sub) return
    busy.value = true
    try {
      await api.pushUnsubscribe(sub.endpoint).catch(() => {})
      await sub.unsubscribe().catch(() => {})
      subscription.value = null
      useToastStore().show('Push-уведомления в этом браузере выключены')
    } finally {
      busy.value = false
      await useAppStore().refresh()
    }
  }

  async function test(kind: 'alert' | 'test' = 'alert') {
    try {
      const r = await api.pushTest(kind)
      useToastStore().show(`Отправлено в браузеров: ${r.sent}`)
    } catch (e) {
      useToastStore().error(e)
    }
  }

  return { registration, subscription, permission, busy, state, init, sync, enable, disable, test }
})
