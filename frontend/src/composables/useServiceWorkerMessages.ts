import { useEventListener } from '@vueuse/core'
import type { FeedEvent } from '@/api/types'
import { useAlarmStore } from '@/stores/alarm'
import { useAppStore } from '@/stores/app'
import { useEventsStore } from '@/stores/events'

interface PushPayload {
  title?: string
  body?: string
  kind?: string
  url?: string | null
  event_id?: number | null
}

/**
 * Сообщения от Service Worker:
 *  - push пришёл, а SSE сейчас отключён → показываем тревогу на странице;
 *  - клик по уведомлению → подсвечиваем событие в ленте.
 */
export function useServiceWorkerMessages() {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return
  const app = useAppStore()
  const alarm = useAlarmStore()
  const events = useEventsStore()

  useEventListener(navigator.serviceWorker, 'message', (m: MessageEvent) => {
    const d = (m.data ?? {}) as { type?: string; payload?: PushPayload; eventId?: number }
    if (d.type === 'push' && d.payload?.kind === 'alert' && !app.online) {
      const p = d.payload
      const ev: FeedEvent = {
        id: p.event_id ?? null, kind: 'alert', title: p.title ?? '', body: p.body ?? '', url: p.url ?? null,
        watch_id: null, at: new Date().toISOString(), data: {},
      }
      alarm.show(ev)
    }
    if (d.type === 'focus-event' && d.eventId) {
      events.highlightId = d.eventId
      setTimeout(() => { if (events.highlightId === d.eventId) events.highlightId = null }, 4000)
    }
  })
}
