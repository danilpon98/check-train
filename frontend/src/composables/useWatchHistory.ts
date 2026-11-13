import { type Ref, ref, watch } from 'vue'
import { api } from '@/api/endpoints'
import type { HistoryRow } from '@/api/types'

/** Больше точек график не различит даже на широком мониторе; остальное сервер сожмёт. */
export const CHART_MAX_POINTS = 600

/**
 * История проверок поезда за выбранный период — для графика, сжатая на сервере
 * (размер ответа не растёт с возрастом истории). Перезапрашивается при смене периода
 * и после каждой новой проверки (меняется lastCheckAt). Устаревшие ответы отбрасываются.
 */
export function useWatchHistory(watchId: Ref<string>, hours: Ref<number>, lastCheckAt: Ref<string | null>) {
  const rows = ref<HistoryRow[]>([])
  const loading = ref(false)
  const error = ref('')
  let seq = 0

  async function load() {
    const my = ++seq
    loading.value = true
    try {
      const data = await api.history(watchId.value, hours.value, CHART_MAX_POINTS)
      if (my !== seq) return
      rows.value = data
      error.value = ''
    } catch (e) {
      if (my === seq) error.value = e instanceof Error ? e.message : String(e)
    } finally {
      if (my === seq) loading.value = false
    }
  }

  watch([watchId, hours, lastCheckAt], load, { immediate: true })
  return { rows, loading, error, reload: load }
}
