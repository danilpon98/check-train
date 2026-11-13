import { request } from './client'
import type { AppState, CheckRow, FeedEvent, HistoryRow, Settings, SettingsPatch, Watch, WatchPreview } from './types'

const wid = (id: string) => encodeURIComponent(id)

export interface AuthStatus {
  required: boolean
  authenticated: boolean
  remember_days: number
}

export const api = {
  authStatus: () => request<AuthStatus>('GET', '/api/auth/status'),
  login: (password: string, remember: boolean) => request<{ ok: true }>('POST', '/api/auth/login', { password, remember }),
  logout: () => request<{ ok: true }>('POST', '/api/auth/logout'),
  logoutAll: () => request<{ ok: true }>('POST', '/api/auth/logout-all'),

  state: () => request<AppState>('GET', '/api/state'),

  /** история для графика; maxPoints — сервер сожмёт её под ширину экрана */
  history: (id: string, hours: number, maxPoints = 0) =>
    request<HistoryRow[]>('GET', `/api/history/${wid(id)}?hours=${hours}&max_points=${maxPoints}`),

  /** журнал проверок для таблицы: от новых к старым, курсором по id */
  checks: (id: string, opts: { before?: number | null; after?: number | null; limit?: number } = {}) => {
    const q = new URLSearchParams({ limit: String(opts.limit ?? 20) })
    if (opts.before) q.set('before', String(opts.before))
    if (opts.after) q.set('after', String(opts.after))
    return request<CheckRow[]>('GET', `/api/checks/${wid(id)}?${q}`)
  },

  events: (opts: { kinds?: string; before?: number | null; limit?: number } = {}) => {
    const q = new URLSearchParams({ limit: String(opts.limit ?? 40) })
    if (opts.kinds) q.set('kinds', opts.kinds)
    if (opts.before) q.set('before', String(opts.before))
    return request<FeedEvent[]>('GET', `/api/events?${q}`)
  },

  previewWatch: (url: string, name?: string) => request<WatchPreview>('POST', '/api/watches/preview', { url, name }),
  addWatch: (url: string, name?: string) => request<Watch>('POST', '/api/watches', { url, name }),
  patchWatch: (id: string, patch: { name?: string | null; enabled?: boolean }) =>
    request<Watch>('PATCH', `/api/watches/${wid(id)}`, patch),
  deleteWatch: (id: string) => request<{ ok: true }>('DELETE', `/api/watches/${wid(id)}`),
  checkWatch: (id: string) => request<Watch>('POST', `/api/watches/${wid(id)}/check`),
  checkAll: () => request<{ ok: true }>('POST', '/api/check-all'),

  settings: () => request<Settings>('GET', '/api/settings'),
  saveSettings: (patch: SettingsPatch) => request<Settings>('PUT', '/api/settings', patch),
  testTelegram: (token: string, chat_id: string) =>
    request<{ ok: true; bot: string }>('POST', '/api/telegram/test', { token, chat_id }),

  pushSubscribe: (subscription: PushSubscriptionJSON) => request('POST', '/api/push/subscribe', { subscription }),
  pushUnsubscribe: (endpoint: string) => request('POST', '/api/push/unsubscribe', { endpoint }),
  pushTest: (kind: 'alert' | 'test') => request<{ sent: number; failed: number }>('POST', '/api/push/test', { kind }),
}
