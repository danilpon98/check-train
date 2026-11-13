import { describe, expect, it } from 'vitest'
import type { Car } from '@/api/types'
import { areaPath, makeScales, nearestPoint, niceMax, splitHistory, stepPath, xTicks } from './chart'
import { ago, cabinLabel, duration, fmtKZ, plural, seats, stripLeadingEmoji } from './format'
import { buildSeatMap, seatTitle } from './seatmap'

describe('format', () => {
  it('склоняет «место»', () => {
    expect([1, 2, 5, 11, 12, 21, 22, 25].map(seats)).toEqual([
      '1 место', '2 места', '5 мест', '11 мест', '12 мест', '21 место', '22 места', '25 мест',
    ])
    expect(plural(3, 'кабинка', 'кабинки', 'кабинок')).toBe('кабинки')
  })

  it('форматирует длительность', () => {
    expect(duration(65)).toBe('1:05')
    expect(duration(3 * 3600 + 5 * 60)).toBe('3 ч 05 мин')
    expect(duration(15 * 86400 + 4 * 3600)).toBe('15 д 4 ч')
    expect(duration(-5)).toBe('0:00')
  })

  it('показывает время отправления в UTC+5 независимо от пояса браузера', () => {
    expect(fmtKZ('2026-11-27T23:50:00+05:00')).toBe('27 ноя 23:50')
    expect(fmtKZ('2026-11-27T18:50:00Z')).toBe('27 ноя 23:50')
  })

  it('«N мин назад»', () => {
    const now = Date.parse('2026-11-13T12:00:00Z')
    expect(ago(null, now)).toBe('никогда')
    expect(ago('2026-11-13T11:59:30Z', now)).toBe('только что')
    expect(ago('2026-11-13T11:45:00Z', now)).toBe('15 мин назад')
  })

  it('прочее', () => {
    expect(cabinLabel(['13', '14', '15', '16'])).toBe('13–16')
    expect(stripLeadingEmoji('📋 Отчёт 09:40')).toBe('Отчёт 09:40')
    expect(stripLeadingEmoji('⚠️ Ошибка')).toBe('Ошибка')
    expect(stripLeadingEmoji('Без эмодзи')).toBe('Без эмодзи')
  })
})

describe('seatmap', () => {
  const car: Pick<Car, 'layout_cabins' | 'layout_sides' | 'free_numbers' | 'free_cabins'> = {
    layout_cabins: [['1', '2', '3', '4'], ['5', '6', '7', '8']],
    layout_sides: [['37', '38'], ['39', '40']],
    free_numbers: ['5', '6', '7', '8', '38'],
    free_cabins: [{ seats: ['5', '6', '7', '8'], for_disabled: false }],
  }

  it('кладёт верхние полки сверху, боковые — под кабинкой', () => {
    const [c1, c2] = buildSeatMap(car)
    expect(c1.seats.map((s) => s.number)).toEqual(['2', '4', '1', '3'])
    expect(c1.seats.map((s) => s.lower)).toEqual([false, false, true, true])
    expect(c1.sides.map((s) => [s.number, s.free])).toEqual([['37', false], ['38', true]])
    expect(c1.fullyFree).toBe(false)
    expect(c2.fullyFree).toBe(true)
  })

  it('купе без боковых мест', () => {
    const [c] = buildSeatMap({ ...car, layout_sides: [] })
    expect(c.sides).toEqual([])
  })

  it('подпись места', () => {
    expect(seatTitle({ number: '37', free: true, lower: true, side: true })).toBe('Место 37 — боковое нижнее, свободно')
  })
})

describe('chart', () => {
  const rows = [
    { at: '2026-11-13T10:00:00Z', ok: 1, total_free: 75, cars: 8, cabins: 0, error: null },
    { at: '2026-11-13T10:15:00Z', ok: 0, total_free: null, cars: null, cabins: null, error: 'HTTP 503' },
    { at: '2026-11-13T10:30:00Z', ok: 1, total_free: 80, cars: 8, cabins: 1, error: null },
    { at: '2026-11-13T10:45:00Z', ok: 1, total_free: 78, cars: 8, cabins: 0, error: null },
  ]
  const box = { width: 600, height: 180, margin: { l: 34, r: 12, t: 10, b: 22 } }

  it('разделяет успешные и неудачные проверки', () => {
    const { points, failures } = splitHistory(rows)
    expect(points.map((p) => p.v)).toEqual([75, 80, 78])
    expect(failures).toHaveLength(1)
  })

  it('niceMax', () => {
    expect([3, 7, 18, 82, 88, 130].map(niceMax)).toEqual([4, 10, 20, 100, 100, 200])
  })

  it('масштабы и ступенчатая линия', () => {
    const { points } = splitHistory(rows)
    const now = Date.parse('2026-11-13T11:00:00Z')
    const s = makeScales(points, box, 0, now)
    expect(s.x(points[0].t)).toBe(34)
    expect(s.x(points[2].t)).toBe(600 - 12)
    expect(s.y(0)).toBe(180 - 22)
    expect(s.vmax).toBe(100)
    const line = stepPath(points, s, now)
    expect(line.startsWith(`M34,${s.y(75)}`)).toBe(true)
    expect(line).toMatch(/H[\d.]+V[\d.]+H[\d.]+V[\d.]+H[\d.]+$/)
    expect(areaPath(line, points, s).endsWith('Z')).toBe(true)
    expect(nearestPoint(points, s, 590).v).toBe(78)
  })

  it('линия не уходит левее первой точки, если «сейчас» раньше последней проверки', () => {
    const { points } = splitHistory(rows)
    const last = points[points.length - 1].t
    const s = makeScales(points, box, 24, last - 30_000)   // «сейчас», округлённое вниз до минуты
    const xs = [...stepPath(points, s, last - 30_000).matchAll(/[MH](-?[\d.]+)/g)].map((m) => Number(m[1]))
    expect(Math.min(...xs)).toBeGreaterThanOrEqual(box.margin.l)
    expect(Math.max(...xs)).toBeLessThanOrEqual(box.width - box.margin.r)
  })

  it('окно «последние N часов» не раньше первой проверки', () => {
    const { points } = splitHistory(rows)
    const now = Date.parse('2026-11-13T11:00:00Z')
    const s = makeScales(points, box, 24, now)
    expect(s.tmin).toBe(points[0].t)
    expect(s.tmax).toBe(now)
  })

  it('подписи оси без повторов', () => {
    const { points } = splitHistory(rows.slice(0, 1).concat({ ...rows[0], at: '2026-11-13T10:01:00Z' }))
    const s = makeScales(points, box, 0, Date.now())
    const labels = xTicks(s, 600, 34).map((t) => t.label)
    expect(new Set(labels).size).toBe(labels.length)
  })
})
