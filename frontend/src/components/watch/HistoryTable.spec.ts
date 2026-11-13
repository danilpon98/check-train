import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CheckRow } from '@/api/types'
import { CHECK_PAGE_SIZE } from '@/composables/useCheckLog'
import { installBrowserMocks, setIntersecting } from '@/test/browserMocks'
import { fmtDateTime } from '@/utils/format'
import HistoryTable from './HistoryTable.vue'

const timeOf = (id: number) => fmtDateTime(new Date(Date.UTC(2026, 10, 13, 0, id)))

// фальшивый сервер: журнал проверок по поездам, отдаёт как /api/checks (от новых к старым)
let db: Record<string, CheckRow[]> = {}
let requests: URL[] = []

function addChecks(watch: string, n: number, startId = 1) {
  const list = db[watch] ?? (db[watch] = [])
  for (let i = 0; i < n; i++) {
    const id = startId + i
    list.push({ id, at: new Date(Date.UTC(2026, 10, 13, 0, id)).toISOString(), ok: id % 10 === 0 ? 0 : 1,
      total_free: 70, cars: 8, cabins: 0, error: id % 10 === 0 ? 'HTTP 503' : null })
  }
}

beforeEach(() => {
  installBrowserMocks()
  db = {}
  requests = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://localhost')
    requests.push(url)
    const watch = decodeURIComponent(url.pathname.split('/').pop()!)
    const before = Number(url.searchParams.get('before') ?? Infinity)
    const after = Number(url.searchParams.get('after') ?? 0)
    const limit = Number(url.searchParams.get('limit'))
    const rows = [...(db[watch] ?? [])].sort((a, b) => b.id - a.id).filter((r) => r.id < before && r.id > after).slice(0, limit)
    return new Response(JSON.stringify(rows), { status: 200 })
  })
})
afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = '' })

async function openTable(watchId = 'w1', lastCheckAt = 't0') {
  const w = mount(HistoryTable, { props: { watchId, lastCheckAt }, attachTo: document.body })
  const details = w.find('details').element as HTMLDetailsElement
  details.open = true
  await w.find('details').trigger('toggle')
  await flushPromises()
  return w
}

const ids = (w: ReturnType<typeof mount>) => w.findAll('tbody tr:not(.sentinel):not(.note)').length

describe('HistoryTable — журнал проверок', () => {
  it('ничего не грузит, пока таблица свёрнута', async () => {
    addChecks('w1', 100)
    mount(HistoryTable, { props: { watchId: 'w1', lastCheckAt: 't0' } })
    await flushPromises()
    expect(requests).toHaveLength(0)
  })

  it('при раскрытии — одна страница, дальше — при прокрутке внутри таблицы', async () => {
    addChecks('w1', 100)
    const w = await openTable()
    expect(ids(w)).toBe(CHECK_PAGE_SIZE)
    expect(requests).toHaveLength(1)
    expect(w.find('tr.fail').exists()).toBe(true)                       // неудачная проверка выделена

    // после подгрузки маркер уезжает вниз
    const sentinel = w.find('tr.sentinel').element as HTMLElement
    vi.mocked(fetch).mockClear()
    let calls = 0
    const orig = vi.mocked(fetch).getMockImplementation()!
    vi.mocked(fetch).mockImplementation(async (...a) => {
      calls++
      sentinel.getBoundingClientRect = () => ({ top: 9999, bottom: 10000, left: 0, right: 0, width: 0, height: 1, x: 0, y: 9999, toJSON() {} })
      return orig(...a)
    })
    setIntersecting(true)
    await flushPromises()
    expect(calls).toBe(1)
    expect(ids(w)).toBe(CHECK_PAGE_SIZE * 2)
    expect(requests.at(-1)!.searchParams.get('before')).toBe('81')      // курсор = id самой старой строки
  })

  it('после новой проверки догружает только новые строки', async () => {
    addChecks('w1', 30)
    const w = await openTable()
    expect(ids(w)).toBe(CHECK_PAGE_SIZE)
    addChecks('w1', 2, 31)
    await w.setProps({ lastCheckAt: 't1' })
    await flushPromises()
    const last = requests.at(-1)!
    expect(last.searchParams.get('after')).toBe('30')                    // только новее самой свежей
    expect(ids(w)).toBe(CHECK_PAGE_SIZE + 2)
    expect(w.find('tbody tr td').text()).toBe(timeOf(32))                // новые — сверху
  })

  it('новые проверки, пришедшие во время подгрузки страницы, не теряются', async () => {
    addChecks('w1', 60)
    const w = await openTable()
    addChecks('w1', 1, 61)
    setIntersecting(true)                                                // началась подгрузка страницы
    await w.setProps({ lastCheckAt: 't1' })                              // и тут пришла проверка
    await flushPromises()
    await flushPromises()
    const rows = w.findAll('tbody tr:not(.sentinel):not(.note)')
    expect(rows[0].find('td').text()).toBe(timeOf(61))                   // id 61 — первым
    expect(requests.some((r) => r.searchParams.get('after') === '60')).toBe(true)
  })

  it('смена поезда сбрасывает журнал', async () => {
    addChecks('w1', 30)
    addChecks('w2', 3)
    const w = await openTable('w1')
    expect(ids(w)).toBe(CHECK_PAGE_SIZE)
    await w.setProps({ watchId: 'w2' })
    await flushPromises()
    expect(ids(w)).toBe(3)
    expect(w.text()).toContain('Это все проверки')
  })
})
