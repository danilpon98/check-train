export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly retryAfter: number | null = null) {
    super(message)
    this.name = 'ApiError'
  }
}

/** Сессия истекла или её нет: интерфейс показывает страницу входа (слушает stores/auth). */
export const UNAUTHORIZED_EVENT = 'trainwatch:unauthorized'
const AUTH_PATHS = ['/api/auth/']

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

/** fetch-обёртка: JSON туда и обратно, текст ошибки из поля detail ответа FastAPI. */
export async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, credentials: 'include', headers: {} }
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }
  let res: Response
  try {
    res = await fetch(path, init)
  } catch {
    throw new ApiError('Нет связи с сервисом', 0)
  }
  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    /* пустой ответ */
  }
  if (!res.ok) {
    if (res.status === 401 && !AUTH_PATHS.some((p) => path.startsWith(p))) {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
    }
    const detail = (data as { detail?: unknown } | null)?.detail
    const ra = Number(res.headers.get('Retry-After'))
    throw new ApiError(typeof detail === 'string' ? detail : `HTTP ${res.status}`, res.status, ra > 0 ? ra : null)
  }
  return data as T
}
