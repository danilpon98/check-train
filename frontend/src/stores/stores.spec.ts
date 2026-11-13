import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { FeedEvent, Settings } from '@/api/types'
import { TEST_ALARM, useAlarmStore } from './alarm'
import { useEventsStore } from './events'
import { b64urlToBytes, bytesToB64url } from './push'
import { useSettingsStore } from './settings'

const ev = (id: number, kind: FeedEvent['kind']): FeedEvent => ({
  id, kind, title: `${kind} ${id}`, body: '', watch_id: 'w', url: null, at: '2026-11-13T10:00:00Z', data: {},
})

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

describe('events store', () => {
  it('живое событие попадает в ленту только если подходит под фильтр и ещё не показано', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('[]', { status: 200 }))
    const s = useEventsStore()
    s.prepend(ev(1, 'report'))
    s.prepend(ev(1, 'report'))
    expect(s.items).toHaveLength(1)
    await s.setFilter('alert')
    expect(fetchMock.mock.calls[0][0]).toContain('kinds=alert')
    s.prepend(ev(2, 'report'))
    s.prepend(ev(3, 'alert'))
    expect(s.items.map((e) => e.id)).toEqual([3])
  })
})

describe('settings store', () => {
  it('маска токена не отправляется, пустое поле — удаляет токен', async () => {
    const saved: Settings = {
      check_interval_minutes: 15, jitter_seconds: 30, retry_delay_seconds: 60, failure_alert_threshold: 3,
      confirm_empty_checks: 2, telegram_enabled: true, telegram_chat_id: ' 42 ', telegram_commands: true,
      telegram_reports: true, quiet_reports: true, push_reports: false,
      telegram_token_set: true, telegram_token_masked: '••••••abcd', telegram_env: false,
    }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(saved), { status: 200 }))
    const s = useSettingsStore()
    await s.load()
    const unchanged = s.patchFromDraft(s.draft!)
    expect(unchanged).not.toHaveProperty('telegram_token')
    expect(unchanged.telegram_chat_id).toBe('42')
    expect(s.patchFromDraft({ ...s.draft!, telegram_token: '' }).telegram_token).toBe('')
    expect(s.patchFromDraft({ ...s.draft!, telegram_token: ' 1:new ' }).telegram_token).toBe('1:new')
  })
})

describe('alarm store', () => {
  it('одну и ту же тревогу не показывает дважды, hide возвращает заголовок', () => {
    const a = useAlarmStore()
    a.show({ ...TEST_ALARM, id: 7 })
    expect(a.current?.title).toBe('ОСВОБОДИЛАСЬ КАБИНКА — 4 МЕСТА! (тест)')
    expect(a.soundNote).not.toBe('')        // в jsdom нет WebAudio — объясняем, почему без звука
    a.hide()
    a.show({ ...TEST_ALARM, id: 7 })
    expect(a.current).toBeNull()
    expect(document.title).toBe('trainwatch')
  })
})

describe('push helpers', () => {
  it('base64url туда и обратно', () => {
    const bytes = new Uint8Array([0, 1, 250, 251, 252, 253, 254, 255])
    expect(b64urlToBytes(bytesToB64url(bytes.buffer))).toEqual(bytes)
  })
})
