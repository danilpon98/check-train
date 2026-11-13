/** Форматирование чисел и времени для русского интерфейса. */

export function plural(n: number, one: string, few: string, many: string): string {
  const n10 = n % 10
  const n100 = n % 100
  if (n10 === 1 && n100 !== 11) return one
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return few
  return many
}

export const seatsWord = (n: number) => plural(n, 'место', 'места', 'мест')
export const seats = (n: number) => `${n} ${seatsWord(n)}`
export const carsIn = (n: number) => `${n} ${plural(n, 'вагоне', 'вагонах', 'вагонах')}`

const pad = (n: number) => String(n).padStart(2, '0')

export function fmtTime(iso: string | number | Date): string {
  const d = new Date(iso)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function fmtDateTime(iso: string | number | Date): string {
  const d = new Date(iso)
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)} ${fmtTime(d)}`
}

const MONTHS = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

/** Время отправления — как на сайте, в поясе Казахстана (UTC+5), независимо от пояса браузера. */
export function fmtKZ(iso: string): string {
  const d = new Date(new Date(iso).getTime() + 5 * 3600e3)
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`
}

export function ago(iso: string | null, now: number = Date.now()): string {
  if (!iso) return 'никогда'
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
  if (s < 60) return 'только что'
  if (s < 3600) return `${Math.floor(s / 60)} мин назад`
  if (s < 86400) return `${Math.floor(s / 3600)} ч ${Math.floor((s % 3600) / 60)} мин назад`
  return fmtDateTime(iso)
}

/** Длительность: «2 д 5 ч», «1 ч 05 мин», «12:07». */
export function duration(sec: number): string {
  const s0 = Math.max(0, Math.round(sec))
  const d = Math.floor(s0 / 86400)
  const h = Math.floor((s0 % 86400) / 3600)
  const m = Math.floor((s0 % 3600) / 60)
  const s = s0 % 60
  if (d) return `${d} д ${h} ч`
  if (h) return `${h} ч ${pad(m)} мин`
  return `${m}:${pad(s)}`
}

export const cabinLabel = (seatsList: string[]) =>
  seatsList.length ? `${seatsList[0]}–${seatsList[seatsList.length - 1]}` : '?'

/** Убирает эмодзи в начале заголовка (в ленте иконка уже стоит отдельно). */
export const stripLeadingEmoji = (s: string) => s.replace(/^\p{Extended_Pictographic}️?\s*/u, '')
