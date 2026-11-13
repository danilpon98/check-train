import { useIntervalFn } from '@vueuse/core'
import { ref } from 'vue'

/**
 * Общие «часы» приложения: одно значение на всех, тикает раз в секунду.
 * Таймеры обратного отсчёта и «N мин назад» пересчитываются от него.
 */
const now = ref(Date.now())
let started = false

export function useNow() {
  if (!started) {
    started = true
    useIntervalFn(() => { now.value = Date.now() }, 1000)
  }
  return now
}
