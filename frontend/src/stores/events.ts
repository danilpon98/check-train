import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/endpoints'
import type { FeedEvent } from '@/api/types'

export const FEED_FILTERS = [
  { value: '', label: 'Все' },
  { value: 'alert', label: 'Тревоги' },
  { value: 'report', label: 'Отчёты' },
  { value: 'error,recovered', label: 'Ошибки' },
] as const

export const PAGE_SIZE = 20

/**
 * Лента событий: курсорная пагинация (before = id последнего загруженного) + живые события из SSE.
 * Загружается только то, что пользователь листает; следующая страница — по кнопке или при прокрутке.
 */
export const useEventsStore = defineStore('events', () => {
  const items = ref<FeedEvent[]>([])
  const filter = ref<string>('')
  const hasMore = ref(false)
  const loading = ref(false)
  /** ошибка подгрузки — показываем и даём повторить, а не крутим запросы бесконечно */
  const error = ref('')
  /** id события, которое нужно подсветить (клик по push-уведомлению) */
  const highlightId = ref<number | null>(null)

  /** номер запроса: ответ на устаревший запрос (сменили фильтр) отбрасывается */
  let seq = 0

  const matches = (e: FeedEvent) => !filter.value || filter.value.split(',').includes(e.kind)

  async function load(reset = true) {
    // следующая страница, пока предыдущая ещё грузится, — дубль (частые срабатывания прокрутки)
    if (!reset && (loading.value || !hasMore.value)) return
    const my = ++seq
    loading.value = true
    error.value = ''
    try {
      const before = reset ? null : items.value[items.value.length - 1]?.id ?? null
      const list = await api.events({ kinds: filter.value || undefined, before, limit: PAGE_SIZE })
      if (my !== seq) return
      if (reset) {
        items.value = list
      } else {
        // между страницами могли прийти живые события — не дублируем
        const seen = new Set(items.value.map((e) => e.id))
        items.value = [...items.value, ...list.filter((e) => !seen.has(e.id))]
      }
      hasMore.value = list.length === PAGE_SIZE
    } catch (e) {
      if (my === seq) error.value = e instanceof Error ? e.message : String(e)
    } finally {
      if (my === seq) loading.value = false
    }
  }

  const loadMore = () => load(false)

  function setFilter(v: string) {
    filter.value = v
    return load(true)
  }

  function prepend(e: FeedEvent) {
    if (!matches(e) || items.value.some((x) => x.id === e.id)) return
    items.value = [e, ...items.value]
  }

  return { items, filter, hasMore, loading, error, highlightId, load, loadMore, setFilter, prepend }
})
