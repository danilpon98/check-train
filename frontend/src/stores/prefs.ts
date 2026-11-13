import { useLocalStorage } from '@vueuse/core'
import { defineStore } from 'pinia'

/**
 * Личные предпочтения этого браузера (localStorage). Если хранилище недоступно
 * (приватный режим, запрет cookies) — работают значения по умолчанию.
 */
export const usePrefsStore = defineStore('prefs', () => {
  const opts = { onError: () => {} }
  const sound = useLocalStorage('tw:sound', true, opts)
  const skipTelegram = useLocalStorage('tw:skipTelegram', false, opts)
  /** ключ находок, для которых баннер скрыт — покажется снова при новой находке */
  const heroDismissed = useLocalStorage('tw:heroDismissed', '', opts)
  /** диапазон графика (часы) по каждому поезду; 0 — вся история */
  const ranges = useLocalStorage<Record<string, number>>('tw:ranges', {}, opts)

  const rangeFor = (watchId: string) => ranges.value[watchId] ?? 48
  const setRange = (watchId: string, hours: number) => {
    ranges.value = { ...ranges.value, [watchId]: hours }
  }

  return { sound, skipTelegram, heroDismissed, ranges, rangeFor, setRange }
})
