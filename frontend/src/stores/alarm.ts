import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { FeedEvent } from '@/api/types'
import { playSiren } from '@/composables/useSiren'
import { usePrefsStore } from './prefs'
import { usePushStore } from './push'

export interface Alarm {
  id: number | null
  title: string
  subtitle: string
  body: string
  url: string | null
}

const REPEAT_MS = 4000
const MAX_REPEATS = 15
const APP_TITLE = 'trainwatch'

export const TEST_ALARM: FeedEvent = {
  id: null,
  kind: 'alert',
  title: '🚨 ОСВОБОДИЛАСЬ КАБИНКА — 4 МЕСТА! (тест)',
  body: 'Вагон 10 (Плацкартный): места 13–16\nВагон 06 (Плацкартный): места 21–24',
  url: 'https://bilet.railways.kz',
  watch_id: null,
  at: new Date().toISOString(),
  data: { watch_title: 'Так будет выглядеть настоящая тревога' },
}

/** Полноэкранная тревога: оверлей + повторяющаяся сирена + мигающий заголовок вкладки. */
export const useAlarmStore = defineStore('alarm', () => {
  const current = ref<Alarm | null>(null)
  /** звук не сыграл — подсказываем почему */
  const soundNote = ref('')
  const shown = new Set<number>()
  let sirenTimer: ReturnType<typeof setInterval> | undefined
  let titleTimer: ReturnType<typeof setInterval> | undefined

  function show(e: FeedEvent) {
    if (e.id !== null) {
      if (shown.has(e.id)) return
      shown.add(e.id)
    }
    current.value = {
      id: e.id,
      title: e.title.replace(/^🚨\s*/u, '').split(' · ')[0],
      subtitle: e.data?.watch_title ?? '',
      body: e.body,
      url: e.url,
    }
    const prefs = usePrefsStore()
    const played = prefs.sound && playSiren()
    soundNote.value = played ? '' : prefs.sound
      ? 'Звук не сыграл: браузер разрешает звук только после клика по странице.'
      : 'Звук выключен в настройках.'

    let n = 0
    clearInterval(sirenTimer)
    sirenTimer = setInterval(() => {
      if (++n > MAX_REPEATS || !current.value) clearInterval(sirenTimer)
      else if (prefs.sound) playSiren()
    }, REPEAT_MS)

    let on = false
    clearInterval(titleTimer)
    titleTimer = setInterval(() => { document.title = (on = !on) ? '🚨 СВОБОДНО! 🚨' : APP_TITLE }, 900)

    // вкладка открыта, но push не включён — системное уведомление средствами страницы
    if (!usePushStore().subscription && typeof Notification !== 'undefined'
      && Notification.permission === 'granted' && document.hidden) {
      try {
        new Notification(e.title, { body: e.body, icon: '/static/icon-192.png', requireInteraction: true, tag: `alert-${e.id}` })
      } catch { /* мобильные браузеры требуют SW */ }
    }
  }

  function hide() {
    current.value = null
    clearInterval(sirenTimer)
    clearInterval(titleTimer)
    document.title = APP_TITLE
  }

  return { current, soundNote, show, hide }
})
