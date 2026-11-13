import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import { api } from '@/api/endpoints'
import type { AppState, Watch } from '@/api/types'
import { cabinLabel, seats } from '@/utils/format'
import { useToastStore } from './toast'

export interface Finding {
  watch: Watch
  kind: 'cabin' | 'car'
  key: string
  car: string
  carType: string
  text: string
}

/** Состояние сервиса: поезда, каналы уведомлений. Источник правды — GET /api/state. */
export const useAppStore = defineStore('app', () => {
  const state = ref<AppState | null>(null)
  /** null — ещё подключаемся к SSE, true/false — есть/нет связи */
  const online = ref<boolean | null>(null)
  /** поезда, проверку которых пользователь только что запустил */
  const checking = reactive(new Set<string>())

  const watches = computed(() => state.value?.watches ?? [])
  const telegram = computed(() => state.value?.telegram ?? null)
  const push = computed(() => state.value?.push ?? null)

  /** Что ищет пользователь и что есть прямо сейчас: свободные кабинки и новые вагоны. */
  const findings = computed<Finding[]>(() => {
    const out: Finding[] = []
    for (const w of watches.value) {
      if (w.status === 'finished') continue
      for (const c of w.cars) {
        for (const cab of c.free_cabins) {
          out.push({
            watch: w, kind: 'cabin', key: `${w.id}:${c.number}:${cab.seats.join(',')}`, car: c.number, carType: c.car_type,
            text: `места ${cabinLabel(cab.seats)}${cab.for_disabled ? ' ♿' : ''}`,
          })
        }
        if (c.is_new) {
          out.push({ watch: w, kind: 'car', key: `${w.id}:new:${c.number}`, car: c.number, carType: c.car_type, text: seats(c.free_seats) })
        }
      }
    }
    return out
  })

  let refreshTimer: ReturnType<typeof setTimeout> | undefined
  let inflight: Promise<void> | null = null

  async function refresh() {
    if (inflight) return inflight
    inflight = (async () => {
      try {
        state.value = await api.state()
      } catch (e) {
        console.warn('state', e)
      } finally {
        inflight = null
      }
    })()
    return inflight
  }

  /** SSE присылает «state» пачками — сводим к одному запросу. */
  function scheduleRefresh(ms = 250) {
    clearTimeout(refreshTimer)
    refreshTimer = setTimeout(refresh, ms)
  }

  const toast = useToastStore()

  async function run<T>(fn: () => Promise<T>, ok?: string): Promise<T | undefined> {
    try {
      const r = await fn()
      if (ok) toast.show(ok)
      return r
    } catch (e) {
      toast.error(e)
      return undefined
    } finally {
      await refresh()
    }
  }

  async function checkWatch(id: string) {
    checking.add(id)
    try {
      await run(() => api.checkWatch(id))
    } finally {
      checking.delete(id)
    }
  }

  async function checkAll() {
    const ids = watches.value.filter((w) => w.enabled && w.status !== 'finished').map((w) => w.id)
    ids.forEach((id) => checking.add(id))
    try {
      await run(() => api.checkAll(), 'Проверка выполнена')
    } finally {
      ids.forEach((id) => checking.delete(id))
    }
  }

  const setEnabled = (id: string, enabled: boolean) =>
    run(() => api.patchWatch(id, { enabled }), enabled ? 'Отслеживание возобновлено' : 'Поставлено на паузу')
  const rename = (id: string, name: string) => run(() => api.patchWatch(id, { name: name.trim() || null }), 'Сохранено')
  const remove = (id: string) => run(() => api.deleteWatch(id), 'Удалено')
  const add = (url: string, name?: string) => run(() => api.addWatch(url, name), 'Поезд добавлен — первая проверка уже идёт')

  return {
    state, online, checking, watches, telegram, push, findings,
    refresh, scheduleRefresh, checkWatch, checkAll, setEnabled, rename, remove, add,
  }
})
