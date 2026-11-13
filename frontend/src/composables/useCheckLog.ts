import { computed, type Ref, ref, shallowRef, watch } from 'vue'
import { api } from '@/api/endpoints'
import type { CheckRow } from '@/api/types'

export const CHECK_PAGE_SIZE = 20

/**
 * Журнал проверок поезда для таблицы.
 *  - ничего не грузит, пока таблица свёрнута (active = false);
 *  - при раскрытии — первая страница, дальше по запросу (бесконечная прокрутка);
 *  - после новой проверки догружает ТОЛЬКО новые строки (after = id самой свежей),
 *    а не всю историю заново;
 *  - при смене поезда — сброс.
 */
export function useCheckLog(watchId: Ref<string>, lastCheckAt: Ref<string | null>, active: Ref<boolean>) {
  // shallowRef: строки не мутируются, глубокая реактивность для сотен строк не нужна
  const rows = shallowRef<CheckRow[]>([])
  const hasMore = ref(false)
  const loading = ref(false)
  const error = ref('')
  const loaded = ref(false)
  let seq = 0
  /** новая проверка пришла, пока шла другая загрузка — догрузить после неё */
  let pendingNewer = false

  const newestId = computed(() => rows.value[0]?.id ?? null)
  const oldestId = computed(() => rows.value[rows.value.length - 1]?.id ?? null)

  async function run(fn: () => Promise<void>) {
    const my = ++seq
    loading.value = true
    error.value = ''
    try {
      await fn()
    } catch (e) {
      if (my === seq) error.value = e instanceof Error ? e.message : String(e)
    } finally {
      if (my === seq) loading.value = false
    }
    if (pendingNewer && my === seq) {
      pendingNewer = false
      void loadNewer()
    }
    return my
  }

  async function loadFirst() {
    const my = seq + 1
    await run(async () => {
      const page = await api.checks(watchId.value, { limit: CHECK_PAGE_SIZE })
      if (my !== seq) return
      rows.value = page
      hasMore.value = page.length === CHECK_PAGE_SIZE
      loaded.value = true
    })
  }

  async function loadMore() {
    if (loading.value || !hasMore.value || !oldestId.value) return
    const my = seq + 1
    await run(async () => {
      const page = await api.checks(watchId.value, { before: oldestId.value, limit: CHECK_PAGE_SIZE })
      if (my !== seq) return
      rows.value = [...rows.value, ...page]
      hasMore.value = page.length === CHECK_PAGE_SIZE
    })
  }

  /** Только новые проверки сверху. Если их накопилось больше страницы — проще перечитать начало. */
  async function loadNewer() {
    if (!loaded.value) return
    if (loading.value) { pendingNewer = true; return }
    if (!newestId.value) return loadFirst()
    const my = seq + 1
    await run(async () => {
      const fresh = await api.checks(watchId.value, { after: newestId.value, limit: CHECK_PAGE_SIZE })
      if (my !== seq || !fresh.length) return
      if (fresh.length === CHECK_PAGE_SIZE) {
        rows.value = fresh
        hasMore.value = true
      } else {
        rows.value = [...fresh, ...rows.value]
      }
    })
  }

  function reset() {
    seq++
    pendingNewer = false
    rows.value = []
    hasMore.value = false
    loaded.value = false
    loading.value = false
    error.value = ''
  }

  watch(watchId, () => { reset(); if (active.value) void loadFirst() })
  watch(active, (on) => { if (on && !loaded.value) void loadFirst() })
  watch(lastCheckAt, () => { if (active.value) void loadNewer() })

  return { rows, hasMore, loading, error, loaded, loadFirst, loadMore, loadNewer }
}
