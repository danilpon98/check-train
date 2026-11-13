/** Геометрия графика «свободные места во времени»: чистые функции без DOM. */
import type { HistoryRow } from '@/api/types'
import { fmtDateTime, fmtTime } from './format'

export interface Point {
  t: number
  v: number
  cabins: number
  cars: number
}

export interface Failure {
  t: number
  error: string | null
}

export interface ChartBox {
  width: number
  height: number
  margin: { l: number; r: number; t: number; b: number }
}

export function splitHistory(rows: HistoryRow[]): { points: Point[]; failures: Failure[] } {
  const points: Point[] = []
  const failures: Failure[] = []
  for (const r of rows) {
    const t = new Date(r.at).getTime()
    if (r.ok && r.total_free !== null) points.push({ t, v: r.total_free, cabins: r.cabins ?? 0, cars: r.cars ?? 0 })
    else if (!r.ok) failures.push({ t, error: r.error })
  }
  return { points, failures }
}

/** «Красивый» верх оси: 4, 5, 10, 20, 25, 50, 100… */
export function niceMax(v: number): number {
  if (v <= 4) return 4
  const p = Math.pow(10, Math.floor(Math.log10(v)))
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p
  return v
}

export interface Scales {
  x: (t: number) => number
  y: (v: number) => number
  tmin: number
  tmax: number
  vmax: number
}

export function makeScales(points: Point[], box: ChartBox, hours: number, now: number): Scales {
  const { width: W, height: H, margin: m } = box
  const first = points[0].t
  const last = points[points.length - 1].t
  // окно «последние N часов», но не раньше первой проверки — иначе график прижат вправо
  const tmin = hours ? Math.max(first, now - hours * 3600e3) : first
  const tmax = Math.max(last, hours ? now : last)
  const vmax = niceMax(Math.max(...points.map((p) => p.v)) * 1.1 || 1)
  return {
    x: (t) => m.l + ((t - tmin) / Math.max(1, tmax - tmin)) * (W - m.l - m.r),
    y: (v) => m.t + (1 - v / vmax) * (H - m.t - m.b),
    tmin,
    tmax,
    vmax,
  }
}

/** Ступенчатая линия: число мест меняется скачком в момент проверки и держится до следующей. */
export function stepPath(points: Point[], s: Scales, untilT: number): string {
  let d = `M${s.x(points[0].t)},${s.y(points[0].v)}`
  for (let i = 1; i < points.length; i++) d += `H${s.x(points[i].t)}V${s.y(points[i].v)}`
  // линия тянется до «сейчас», но никогда не назад (untilT может быть округлён вниз) и не за край
  const end = Math.min(Math.max(untilT, points[points.length - 1].t), s.tmax)
  return d + `H${s.x(end)}`
}

export function areaPath(line: string, points: Point[], s: Scales): string {
  return `${line}V${s.y(0)}H${s.x(points[0].t)}Z`
}

export function yTicks(vmax: number): number[] {
  return [0, 0.25, 0.5, 0.75, 1].map((k) => k * vmax)
}

/** Подписи оси времени; одинаковые соседние подписи убираются. */
export function xTicks(s: Scales, width: number, left: number): { t: number; label: string }[] {
  const n = Math.max(2, Math.min(6, Math.floor((width - left) / 90)))
  const span = s.tmax - s.tmin
  const longRange = span > 36 * 3600e3
  const out: { t: number; label: string }[] = []
  let prev = ''
  for (let i = 0; i < n; i++) {
    const t = s.tmin + (span * i) / (n - 1)
    const label = longRange ? fmtDateTime(t) : fmtTime(t)
    if (label !== prev) out.push({ t, label })
    prev = label
  }
  return out
}

export function nearestPoint(points: Point[], s: Scales, px: number): Point {
  let best = points[0]
  for (const p of points) if (Math.abs(s.x(p.t) - px) < Math.abs(s.x(best.t) - px)) best = p
  return best
}
