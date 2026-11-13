import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { UNAUTHORIZED_EVENT } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import App from '@/App.vue'
import LoginView from './LoginView.vue'

type Reply = { status: number; body: unknown; headers?: Record<string, string> }
let replies: Record<string, Reply[]> = {}
let calls: { path: string; body: unknown }[] = []

function reply(path: string, ...r: Reply[]) {
  replies[path] = r
}

beforeEach(() => {
  setActivePinia(createPinia())
  replies = {}
  calls = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = new URL(String(input), 'http://localhost').pathname
    calls.push({ path, body: init?.body ? JSON.parse(String(init.body)) : null })
    const queue = replies[path]
    const r = queue && queue.length > 1 ? queue.shift()! : queue?.[0] ?? { status: 404, body: { detail: 'нет' } }
    return new Response(JSON.stringify(r.body), { status: r.status, headers: r.headers })
  })
})
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); document.body.innerHTML = '' })

async function typeAndSubmit(w: ReturnType<typeof mount>, pw: string) {
  await w.find('input[type=password]').setValue(pw)
  await w.find('form').trigger('submit')
  await flushPromises()
}

describe('LoginView', () => {
  it('неверный пароль: сообщение, поле очищено, кнопка недоступна до ввода', async () => {
    reply('/api/auth/login', { status: 401, body: { detail: 'Неверный пароль.' } })
    const w = mount(LoginView, { attachTo: document.body })
    expect(w.find('button[type=submit]').attributes('disabled')).toBeDefined()     // пустой пароль
    await typeAndSubmit(w, 'nope')
    expect(w.find('[role=alert]').text()).toContain('Неверный пароль')
    expect((w.find('input[type=password]').element as HTMLInputElement).value).toBe('')
    expect(useAuthStore().authenticated).toBe(false)
  })

  it('отправляет пароль и «запомнить»; успех — вход выполнен', async () => {
    reply('/api/auth/login', { status: 200, body: { ok: true } })
    const w = mount(LoginView)
    await w.find('input[type=checkbox]').setValue(false)
    expect(w.text()).toContain('Запомнить меня на 30 дней')
    expect(w.text()).not.toContain('WEB_PASSWORD')
    await typeAndSubmit(w, 's3cret')
    expect(calls.at(-1)).toEqual({ path: '/api/auth/login', body: { password: 's3cret', remember: false } })
    expect(useAuthStore().authenticated).toBe(true)
  })

  it('блокировка после перебора: обратный отсчёт и недоступная форма', async () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    reply('/api/auth/login', { status: 429, body: { detail: 'Слишком много попыток' }, headers: { 'Retry-After': '120' } })
    const w = mount(LoginView)
    await typeAndSubmit(w, 'nope')
    expect(w.text()).toContain('Повторите через')
    expect(w.text()).toContain('2:00')
    expect(w.find('button[type=submit]').text()).toContain('заблокирован')
    expect(w.find('input[type=password]').attributes('disabled')).toBeDefined()
    vi.advanceTimersByTime(121_000)
    await flushPromises()
    expect(w.find('input[type=password]').attributes('disabled')).toBeUndefined()   // разблокировано
  })

  it('показать/скрыть пароль', async () => {
    const w = mount(LoginView)
    await w.find('button.eye').trigger('click')
    expect(w.find('#tw-password').attributes('type')).toBe('text')
    expect(w.find('button.eye').attributes('aria-pressed')).toBe('true')
  })
})

describe('App — ворота входа', () => {
  it('нужен вход → страница входа; без пароля на сервере → сразу панель', async () => {
    reply('/api/auth/status', { status: 200, body: { required: true, authenticated: false, remember_days: 30 } })
    const w = mount(App, { shallow: true })
    await flushPromises()
    expect(w.findComponent(LoginView).exists()).toBe(true)

    setActivePinia(createPinia())
    reply('/api/auth/status', { status: 200, body: { required: false, authenticated: true, remember_days: 30 } })
    const w2 = mount(App, { shallow: true })
    await flushPromises()
    expect(w2.findComponent(LoginView).exists()).toBe(false)
    expect(w2.findComponent({ name: 'DashboardView' }).exists()).toBe(true)
  })

  it('сессия истекла во время работы (401) → вход с пояснением', async () => {
    reply('/api/auth/status', { status: 200, body: { required: true, authenticated: true, remember_days: 30 } })
    const w = mount(App, { shallow: true })
    await flushPromises()
    expect(w.findComponent(LoginView).exists()).toBe(false)
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
    await flushPromises()
    expect(w.findComponent(LoginView).exists()).toBe(true)
    expect(useAuthStore().reason).toBe('expired')
  })
})
