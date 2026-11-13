/** Раскладка схемы вагона для отрисовки. */
import type { Car } from '@/api/types'

export interface SeatCell {
  number: string
  free: boolean
  /** нечётные места — нижние полки */
  lower: boolean
  side: boolean
}

export interface CabinColumn {
  key: string
  /** порядок отрисовки сетки 2×2: сверху верхние полки, снизу нижние */
  seats: SeatCell[]
  sides: SeatCell[]
  fullyFree: boolean
}

const isLower = (n: string) => Number(n) % 2 === 1

export function buildSeatMap(car: Pick<Car, 'layout_cabins' | 'layout_sides' | 'free_numbers' | 'free_cabins'>): CabinColumn[] {
  const free = new Set(car.free_numbers)
  const full = new Set(car.free_cabins.map((c) => c.seats.join(',')))
  const cell = (n: string, side = false): SeatCell => ({ number: n, free: free.has(n), lower: isLower(n), side })
  return car.layout_cabins.map((cab, i) => {
    // места в кабинке идут [нижнее, верхнее, нижнее, верхнее] → рисуем верхние сверху
    const ordered = cab.length === 4 ? [cab[1], cab[3], cab[0], cab[2]] : cab
    return {
      key: cab.join(','),
      seats: ordered.map((n) => cell(n)),
      sides: (car.layout_sides[i] ?? []).map((n) => cell(n, true)),
      fullyFree: full.has(cab.join(',')),
    }
  })
}

export function seatTitle(c: SeatCell): string {
  const kind = `${c.side ? 'боковое ' : ''}${c.lower ? 'нижнее' : 'верхнее'}`
  return `Место ${c.number} — ${kind}, ${c.free ? 'свободно' : 'занято'}`
}
