import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ApiError, UNAUTHORIZED_EVENT } from '@/api/client'
import { api } from '@/api/endpoints'

export type LoginReason = 'expired' | 'signed-out' | null

/**
 * Вход по паролю. Сессия живёт в HttpOnly-cookie (скрипт её не видит) — здесь только флаги:
 * нужен ли вход вообще (задан ли WEB_PASSWORD) и выполнен ли он.
 */
export const useAuthStore = defineStore('auth', () => {
  /** проверка статуса завершена (до неё показываем заставку, чтобы не мигала страница входа) */
  const checked = ref(false)
  const required = ref(false)
  const authenticated = ref(false)
  const rememberDays = ref(30)
  /** почему показываем вход: сессия истекла во время работы / пользователь вышел */
  const reason = ref<LoginReason>(null)

  async function check() {
    try {
      const s = await api.authStatus()
      required.value = s.required
      authenticated.value = s.authenticated
      rememberDays.value = s.remember_days
    } catch {
      // сервис недоступен — откроется панель, она сама покажет «нет связи» и переподключится
      authenticated.value = true
    } finally {
      checked.value = true
    }
  }

  /** Бросает ApiError: 401 — неверный пароль, 429 — блокировка (retryAfter, сек). */
  async function login(password: string, remember: boolean) {
    await api.login(password, remember)
    reason.value = null
    authenticated.value = true
  }

  async function logout(everywhere = false) {
    try {
      await (everywhere ? api.logoutAll() : api.logout())
    } finally {
      // перезагрузка — самый надёжный способ сбросить всё состояние панели и закрыть поток
      sessionStorage.setItem('tw:reason', 'signed-out')
      location.reload()
    }
  }

  // любой ответ 401 во время работы — сессия истекла
  window.addEventListener(UNAUTHORIZED_EVENT, () => {
    if (!required.value || !authenticated.value) return
    authenticated.value = false
    reason.value = 'expired'
  })
  try {
    if (sessionStorage.getItem('tw:reason') === 'signed-out') reason.value = 'signed-out'
    sessionStorage.removeItem('tw:reason')
  } catch { /* приватный режим */ }

  return { checked, required, authenticated, rememberDays, reason, check, login, logout }
})

export const isLockout = (e: unknown): e is ApiError => e instanceof ApiError && e.status === 429
