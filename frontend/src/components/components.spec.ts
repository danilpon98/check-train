import { createTestingPinia } from './testing'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Car, Watch } from '@/api/types'
import { useAppStore } from '@/stores/app'
import { usePrefsStore } from '@/stores/prefs'
import FindingsHero from './hero/FindingsHero.vue'
import CarTile from './watch/CarTile.vue'
import SeatMap from './watch/SeatMap.vue'
import WatchKpis from './watch/WatchKpis.vue'

function makeCar(over: Partial<Car> = {}): Car {
  return {
    direction: 'forward', number: '10', car_type: 'Плацкартный', service_class: '3П', free_seats: 6,
    price: '4 564,00 KZT', signs: '', free_cabins: [],
    layout_cabins: [['1', '2', '3', '4'], ['5', '6', '7', '8']], layout_sides: [['37', '38'], ['39', '40']],
    free_numbers: ['5', '6', '7', '8', '37', '40'], is_new: false, first_seen: null, ...over,
  }
}

function makeWatch(cars: Car[]): Watch {
  return {
    id: 'w1', name: null, title: 'Поезд 046Х', url: 'https://bilet.railways.kz/x', enabled: true, train: '046Х',
    departure: null, train_info: null, carrier: null, route: 'ТУРКЕСТАН → ПАВЛОДАР', departure_text: null,
    arrival_text: null, status: 'ok', started_at: null, last_check_at: null, last_ok_at: null, next_check_at: null,
    consecutive_failures: 0, last_error: null, pending_empty: 0, cars, absent_known: [],
    totals: { free: 0, cars: cars.length, cabins: 0, known: cars.length, new_cars: 0 },
  }
}

describe('SeatMap', () => {
  it('рисует кабинки, боковые места и подсвечивает целиком свободную', () => {
    const car = makeCar({ free_cabins: [{ seats: ['5', '6', '7', '8'], for_disabled: false }] })
    const w = mount(SeatMap, { props: { car } })
    expect(w.findAll('.col')).toHaveLength(2)
    expect(w.findAll('.s')).toHaveLength(12)
    expect(w.findAll('.s.f')).toHaveLength(6)
    expect(w.findAll('.cab.full')).toHaveLength(1)
    expect(w.find('.s').attributes('title')).toBe('Место 2 — верхнее, занято')
  })
})

describe('CarTile', () => {
  it('показывает метки «НОВЫЙ» и число кабинок', () => {
    const car = makeCar({ is_new: true, first_seen: '2026-11-13T10:00:00Z', free_cabins: [{ seats: ['5', '6', '7', '8'], for_disabled: true }] })
    const w = mount(CarTile, { props: { car } })
    expect(w.text()).toContain('НОВЫЙ')
    expect(w.text()).toContain('1 кабинка')
    expect(w.text()).toContain('Кабинки целиком: 5–8 ♿')
    expect(w.text()).toContain('6мест')
    expect(w.classes()).toContain('has-cabin')
  })
})

describe('WatchKpis', () => {
  it('подсвечивает кабинки и новые вагоны, только когда они есть', () => {
    const w = mount(WatchKpis, { props: { totals: { free: 75, cars: 8, cabins: 2, known: 9, new_cars: 0 } } })
    const tiles = w.findAll('.kpi')
    expect(tiles.map((t) => t.classes().includes('hot'))).toEqual([false, false, true, false])
    expect(tiles[2].text()).toContain('2свободные кабинки')
    expect(tiles[3].text()).toContain('всего известно 9')
  })
})

describe('FindingsHero', () => {
  it('появляется при свободной кабинке и скрывается до следующей находки', async () => {
    const pinia = createTestingPinia()
    const app = useAppStore(pinia)
    const prefs = usePrefsStore(pinia)
    const w = mount(FindingsHero, { global: { plugins: [pinia] } })
    expect(w.find('.hero').exists()).toBe(false)

    app.state = {
      server: { version: '2', started_at: '', now: '', interval_minutes: 15 },
      telegram: { enabled: false, configured: false, has_token: false, has_chat: false, source: 'ui', bot_username: null, last_error: null, last_sent_at: null, queue: 0, seen_chats: [] },
      push: { public_key: null, subscriptions: 0, last_error: null, reports: false },
      watches: [makeWatch([makeCar({ free_cabins: [{ seats: ['13', '14', '15', '16'], for_disabled: false }] })])],
    }
    await w.vm.$nextTick()
    expect(w.find('.hero').text()).toContain('Есть свободная кабинка')
    expect(w.text()).toContain('Вагон 10 (Плацкартный): места 13–16')
    expect(w.find('a').attributes('href')).toBe('https://bilet.railways.kz/x')

    await w.find('.hide').trigger('click')
    expect(w.find('.hero').exists()).toBe(false)
    expect(prefs.heroDismissed).toContain('13,14,15,16')
  })
})
