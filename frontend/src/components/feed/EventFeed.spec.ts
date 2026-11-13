import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { FeedEvent } from '@/api/types'
import { PAGE_SIZE, useEventsStore } from '@/stores/events'
import { installBrowserMocks, media, setIntersecting as sentinelVisible } from '@/test/browserMocks'
import EventFeed from './EventFeed.vue'

// ---- фальшивый API: 50 событий, отдаём страницами по курсору before ----
const ALL: FeedEvent[] = Array.from({ length: 50 }, (_, i) => ({
  id: 50 - i, kind: 'report', title: `Отчёт ${50 - i}`, body: '', watch_id: 'w', url: null,
  at: '2026-11-13T10:00:00Z', data: {},
}))
let requests: URL[] = []
/** вызывается на каждый запрос — чтобы имитировать «страница догрузилась и маркер уехал вниз» */
let onRequest: (() => void) | null = null

function installFetch() {
  requests = []
  onRequest = null
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost')
    requests.push(url)
    onRequest?.()
    const before = Number(url.searchParams.get('before') ?? Infinity)
    const limit = Number(url.searchParams.get('limit'))
    return new Response(JSON.stringify(ALL.filter((e) => (e.id ?? 0) < before).slice(0, limit)), { status: 200 })
  })
}

async function mountFeed() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useEventsStore()
  const w = mount(EventFeed, { global: { plugins: [pinia] }, attachTo: document.body })
  await store.load(true)
  await flushPromises()
  return { w, store }
}

beforeEach(() => { installBrowserMocks(); installFetch() })
afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = '' })

describe('EventFeed — десктоп: бесконечная прокрутка', () => {
  beforeEach(() => { media.desktop = true })

  it('сначала одна страница; при прокрутке до конца — следующая, и только одна', async () => {
    const { w, store } = await mountFeed()
    expect(store.items).toHaveLength(PAGE_SIZE)
    expect(w.find('button.more').exists()).toBe(false)          // кнопки нет
    expect(w.find('.sentinel').exists()).toBe(true)

    onRequest = () => sentinelVisible(false)                     // догрузили — маркер уехал вниз
    sentinelVisible()
    await flushPromises()
    expect(store.items).toHaveLength(PAGE_SIZE * 2)
    expect(requests.at(-1)!.searchParams.get('before')).toBe('31')   // курсор = id последнего
    expect(requests).toHaveLength(2)
  })

  it('одна прокрутка — одна страница, даже пока IntersectionObserver не успел сообщить об уходе маркера', async () => {
    const { w, store } = await mountFeed()
    const el = w.find('.sentinel').element as HTMLElement
    // после подгрузки маркер фактически ниже экрана, но IO ещё «думает», что он виден
    onRequest = () => {
      el.getBoundingClientRect = () => ({ top: 5000, bottom: 5001, left: 0, right: 0, width: 0, height: 1, x: 0, y: 5000, toJSON() {} })
    }
    sentinelVisible()
    await flushPromises()
    await flushPromises()
    expect(store.items).toHaveLength(PAGE_SIZE * 2)
    expect(requests).toHaveLength(2)
  })

  it('если список короче контейнера и маркер остаётся видимым — догружает до конца', async () => {
    const { w, store } = await mountFeed()
    sentinelVisible()                                            // IO сработал один раз и больше не сработает
    await flushPromises()
    expect(store.items).toHaveLength(50)
    expect(requests.map((r) => r.searchParams.get('before'))).toEqual([null, '31', '11'])
    expect(store.hasMore).toBe(false)
    expect(w.text()).toContain('Это все события')
    const before = requests.length
    sentinelVisible()
    await flushPromises()
    expect(requests.length).toBe(before)                          // больше не запрашивает
  })

  it('не грузит, пока маркер не виден', async () => {
    const { store } = await mountFeed()
    sentinelVisible(false)
    await flushPromises()
    expect(store.items).toHaveLength(PAGE_SIZE)
    expect(requests).toHaveLength(1)
  })
})

describe('EventFeed — мобильный: кнопка «Показать ещё»', () => {
  beforeEach(() => { media.desktop = false })

  it('грузит следующую страницу только по кнопке', async () => {
    const { w, store } = await mountFeed()
    expect(w.find('.sentinel').exists()).toBe(false)
    sentinelVisible()
    await flushPromises()
    expect(store.items).toHaveLength(PAGE_SIZE)                   // прокрутка ничего не грузит

    await w.find('button.more').trigger('click')
    await flushPromises()
    expect(store.items).toHaveLength(PAGE_SIZE * 2)
    await w.find('button.more').trigger('click')
    await flushPromises()
    expect(store.items).toHaveLength(50)
    expect(w.find('button.more').exists()).toBe(false)            // всё загружено — кнопка исчезла
  })
})

describe('events store — пагинация', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('параллельные запросы следующей страницы не дублируются', async () => {
    const store = useEventsStore()
    await store.load(true)
    await Promise.all([store.loadMore(), store.loadMore(), store.loadMore()])
    expect(requests).toHaveLength(2)
    expect(new Set(store.items.map((e) => e.id)).size).toBe(store.items.length)
  })

  it('ответ на устаревший фильтр отбрасывается', async () => {
    const store = useEventsStore()
    const p1 = store.setFilter('report')
    const p2 = store.setFilter('alert')                           // пользователь быстро переключил
    await Promise.all([p1, p2])
    expect(store.filter).toBe('alert')
    expect(store.items).toHaveLength(PAGE_SIZE)                   // применён последний ответ
    expect(requests.at(-1)!.searchParams.get('kinds')).toBe('alert')
  })

  it('живое событие, пришедшее между страницами, не дублируется', async () => {
    const store = useEventsStore()
    await store.load(true)
    store.prepend({ ...ALL[0], id: 51 })
    await store.loadMore()
    expect(store.items.filter((e) => e.id === 51)).toHaveLength(1)
    expect(store.items).toHaveLength(PAGE_SIZE * 2 + 1)
  })

  it('ошибка останавливает подгрузку до повтора', async () => {
    const store = useEventsStore()
    await store.load(true)
    vi.mocked(fetch).mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'сервис недоступен' }), { status: 503 }))
    await store.loadMore()
    expect(store.error).toBe('сервис недоступен')
    expect(store.items).toHaveLength(PAGE_SIZE)
  })
})
