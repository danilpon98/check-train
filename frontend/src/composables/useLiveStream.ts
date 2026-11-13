import { onBeforeUnmount } from 'vue'
import type { StreamMessage } from '@/api/types'
import { useAlarmStore } from '@/stores/alarm'
import { useAppStore } from '@/stores/app'
import { useEventsStore } from '@/stores/events'

/**
 * Живое соединение с сервисом (Server-Sent Events, /api/stream) — ОДНО на весь браузер.
 *
 * Chrome держит не больше 6 одновременных HTTP/1.1-соединений к одному хосту на все вкладки.
 * Если каждая вкладка откроет свой SSE-поток, седьмая вкладка не сможет загрузить даже данные.
 * Поэтому вкладки выбирают «ведущую» через Web Locks: только она держит EventSource и пересылает
 * сообщения остальным через BroadcastChannel. Закрыли ведущую — браузер отдаёт блокировку следующей.
 */
const LOCK = 'trainwatch:sse-leader'
const CHANNEL = 'trainwatch:stream'

type Relay =
  | { kind: 'msg'; data: string }
  | { kind: 'status'; online: boolean; opened?: boolean }
  | { kind: 'hello' }

export function useLiveStream() {
  const app = useAppStore()
  const events = useEventsStore()
  const alarm = useAlarmStore()

  let es: EventSource | null = null
  let channel: BroadcastChannel | null = null
  let releaseLock: (() => void) | null = null
  let isLeader = false

  /** Обработка сообщения потока — одинаково в ведущей и ведомых вкладках. */
  function handle(raw: string) {
    let msg: StreamMessage
    try {
      msg = JSON.parse(raw)
    } catch {
      return
    }
    if (msg.type === 'state') app.scheduleRefresh()
    else if (msg.type === 'event') {
      events.prepend(msg.event)
      if (msg.event.kind === 'alert') alarm.show(msg.event)
      app.scheduleRefresh(100)
    }
  }

  /** Связь (пере)установлена — перечитываем всё, чтобы не потерять случившееся во время разрыва. */
  function onOpened() {
    app.online = true
    void app.refresh()
    void events.load(true)
  }

  /**
   * Короткий обрыв — норма: сервер сам переоткрывает поток раз в 10 минут (прокси хостинга
   * рвут долгие запросы), браузер переподключается за ~3 с. «Нет связи» показываем, только если
   * переподключиться не удалось за OFFLINE_GRACE_MS — иначе плашка мигала бы без причины.
   */
  const OFFLINE_GRACE_MS = 6000
  let offlineTimer: ReturnType<typeof setTimeout> | undefined

  function openEventSource(relay: boolean) {
    es = new EventSource('/api/stream')
    es.onopen = () => {
      clearTimeout(offlineTimer)
      offlineTimer = undefined
      onOpened()
      if (relay) channel?.postMessage({ kind: 'status', online: true, opened: true } satisfies Relay)
    }
    es.onerror = () => {
      if (offlineTimer || app.online === false) return
      offlineTimer = setTimeout(() => {
        offlineTimer = undefined
        app.online = false
        if (relay) channel?.postMessage({ kind: 'status', online: false } satisfies Relay)
      }, OFFLINE_GRACE_MS)
    }
    es.onmessage = (m) => {
      handle(m.data)
      if (relay) channel?.postMessage({ kind: 'msg', data: m.data } satisfies Relay)
    }
  }

  const canShare = typeof BroadcastChannel !== 'undefined' && typeof navigator !== 'undefined' && !!navigator.locks

  if (!canShare) {
    openEventSource(false)            // старый браузер — своё соединение, как раньше
  } else {
    channel = new BroadcastChannel(CHANNEL)
    channel.onmessage = (m: MessageEvent<Relay>) => {
      const d = m.data
      if (isLeader) {
        // новая вкладка спрашивает, есть ли связь
        if (d.kind === 'hello' && es) channel!.postMessage({ kind: 'status', online: es.readyState === EventSource.OPEN } satisfies Relay)
        return
      }
      if (d.kind === 'msg') handle(d.data)
      else if (d.kind === 'status') {
        if (d.online && (d.opened || app.online !== true)) onOpened()
        else app.online = d.online
      }
    }
    channel.postMessage({ kind: 'hello' } satisfies Relay)

    // запрос ждёт, пока блокировка освободится; держим её, пока вкладка жива
    void navigator.locks.request(LOCK, () => new Promise<void>((resolve) => {
      releaseLock = resolve
      isLeader = true
      openEventSource(true)
    }))
  }

  onBeforeUnmount(() => {
    clearTimeout(offlineTimer)
    es?.close()
    channel?.close()
    releaseLock?.()
  })
}
