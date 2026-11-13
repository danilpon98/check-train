import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/endpoints'
import type { Settings, SettingsPatch } from '@/api/types'
import { useAppStore } from './app'

/** Форма настроек: черновик редактируется локально, сохраняется одним PUT. */
export interface SettingsDraft {
  check_interval_minutes: number
  jitter_seconds: number
  retry_delay_seconds: number
  failure_alert_threshold: number
  confirm_empty_checks: number
  telegram_enabled: boolean
  telegram_token: string
  telegram_chat_id: string
  telegram_commands: boolean
  telegram_reports: boolean
  quiet_reports: boolean
  push_reports: boolean
}

function toDraft(s: Settings): SettingsDraft {
  return {
    check_interval_minutes: s.check_interval_minutes,
    jitter_seconds: s.jitter_seconds,
    retry_delay_seconds: s.retry_delay_seconds,
    failure_alert_threshold: s.failure_alert_threshold,
    confirm_empty_checks: s.confirm_empty_checks,
    telegram_enabled: s.telegram_enabled,
    telegram_token: s.telegram_token_masked,
    telegram_chat_id: s.telegram_chat_id,
    telegram_commands: s.telegram_commands,
    telegram_reports: s.telegram_reports,
    quiet_reports: s.quiet_reports,
    push_reports: s.push_reports,
  }
}

export const useSettingsStore = defineStore('settings', () => {
  const saved = ref<Settings | null>(null)
  const draft = ref<SettingsDraft | null>(null)
  const error = ref('')
  const saving = ref(false)

  async function load() {
    error.value = ''
    saved.value = await api.settings()
    draft.value = toDraft(saved.value)
  }

  function patchFromDraft(d: SettingsDraft): SettingsPatch {
    const { telegram_token, ...rest } = d
    const patch: SettingsPatch = { ...rest, telegram_chat_id: d.telegram_chat_id.trim() }
    // маска «••••1234» означает «не менять»; пустое поле — удалить токен
    if (telegram_token.trim() !== (saved.value?.telegram_token_masked ?? '')) patch.telegram_token = telegram_token.trim()
    return patch
  }

  async function save(): Promise<boolean> {
    if (!draft.value) return false
    saving.value = true
    error.value = ''
    try {
      saved.value = await api.saveSettings(patchFromDraft(draft.value))
      draft.value = toDraft(saved.value)
      await useAppStore().refresh()
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      return false
    } finally {
      saving.value = false
    }
  }

  return { saved, draft, error, saving, load, save, patchFromDraft }
})
