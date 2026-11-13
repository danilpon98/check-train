/** Типы ответов бэкенда (trainwatch/web.py). */

export interface Cabin {
  seats: string[]
  for_disabled: boolean
}

export interface Car {
  direction: string
  number: string
  car_type: string
  service_class: string
  free_seats: number
  price: string | null
  signs: string
  free_cabins: Cabin[]
  layout_cabins: string[][]
  layout_sides: string[][]
  free_numbers: string[]
  is_new: boolean
  first_seen: string | null
}

export interface AbsentCar {
  number: string
  first_seen: string
  is_new: boolean
}

export type WatchStatus = 'ok' | 'error' | 'paused' | 'finished' | 'checking' | 'starting'

export interface WatchTotals {
  free: number
  cars: number
  cabins: number
  known: number
  new_cars: number
}

export interface Watch {
  id: string
  name: string | null
  title: string
  url: string
  enabled: boolean
  train: string
  departure: string | null
  train_info: string | null
  carrier: string | null
  route: string | null
  departure_text: string | null
  arrival_text: string | null
  status: WatchStatus
  started_at: string | null
  last_check_at: string | null
  last_ok_at: string | null
  next_check_at: string | null
  consecutive_failures: number
  last_error: string | null
  pending_empty: number
  cars: Car[]
  absent_known: AbsentCar[]
  totals: WatchTotals
}

export interface TelegramStatus {
  enabled: boolean
  configured: boolean
  has_token: boolean
  has_chat: boolean
  source: 'env' | 'ui'
  bot_username: string | null
  last_error: string | null
  last_sent_at: string | null
  queue: number
  seen_chats: { id: string; name: string }[]
}

export interface PushStatus {
  public_key: string | null
  subscriptions: number
  last_error: string | null
  reports: boolean
}

export interface AppState {
  server: { version: string; started_at: string; now: string; interval_minutes: number }
  telegram: TelegramStatus
  push: PushStatus
  watches: Watch[]
}

export type EventKind = 'alert' | 'report' | 'error' | 'recovered' | 'finished' | 'info'

export interface FeedEvent {
  id: number | null
  kind: EventKind
  title: string
  body: string
  watch_id: string | null
  url: string | null
  at: string
  data: {
    text?: string
    watch_title?: string
    new_cars?: string[]
    new_cabins?: { car: string; car_type: string; label: string; seats: string[]; for_disabled: boolean }[]
  }
}

export interface HistoryRow {
  at: string
  ok: number
  total_free: number | null
  cars: number | null
  cabins: number | null
  error: string | null
}

/** Строка журнала проверок (таблица) — с id для курсорной пагинации */
export interface CheckRow extends HistoryRow {
  id: number
}

export interface Settings {
  check_interval_minutes: number
  jitter_seconds: number
  retry_delay_seconds: number
  failure_alert_threshold: number
  confirm_empty_checks: number
  telegram_enabled: boolean
  telegram_chat_id: string
  telegram_commands: boolean
  telegram_reports: boolean
  quiet_reports: boolean
  push_reports: boolean
  // только чтение
  telegram_token_set: boolean
  telegram_token_masked: string
  telegram_env: boolean
}

export type SettingsPatch = Partial<Omit<Settings, 'telegram_token_set' | 'telegram_token_masked' | 'telegram_env'>> & {
  telegram_token?: string
}

export interface WatchPreview {
  id: string
  title: string
  train: string
  departure: string | null
  exists: boolean
  status: 'ok' | 'empty'
  train_info: string | null
  route: string | null
  carrier: string | null
  departure_text: string | null
  cars: Car[]
  totals: { free: number; cars: number; cabins: number }
}

/** Сообщения SSE-потока /api/stream */
export type StreamMessage = { type: 'state' } | { type: 'event'; event: FeedEvent }
