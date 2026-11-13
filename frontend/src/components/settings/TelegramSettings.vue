<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/endpoints'
import BaseButton from '@/components/common/BaseButton.vue'
import CheckboxField from '@/components/common/CheckboxField.vue'
import { useAppStore } from '@/stores/app'
import { useSettingsStore } from '@/stores/settings'
import SettingsSection from './SettingsSection.vue'

const settings = useSettingsStore()
const { draft, saved } = storeToRefs(settings)
const app = useAppStore()

const testing = ref(false)
const result = ref<{ ok: boolean; text: string } | null>(null)

async function test() {
  if (!draft.value) return
  testing.value = true
  result.value = null
  try {
    const r = await api.testTelegram(draft.value.telegram_token.trim(), draft.value.telegram_chat_id.trim())
    result.value = { ok: true, text: `✓ Отправлено через @${r.bot}. Не забудьте сохранить настройки.` }
  } catch (e) {
    result.value = { ok: false, text: `✗ ${e instanceof Error ? e.message : e}` }
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <SettingsSection v-if="draft" title="Telegram">
    <CheckboxField v-model="draft.telegram_enabled" label="Отправлять в Telegram" />
    <p v-if="saved?.telegram_env" class="hint">Токен и chat_id заданы в файле .env — они важнее значений ниже.</p>
    <div class="row">
      <label class="field">Токен бота (от @BotFather)
        <input v-model="draft.telegram_token" autocomplete="off" spellcheck="false" placeholder="123456789:AA…">
      </label>
      <label class="field">chat_id
        <input v-model="draft.telegram_chat_id" autocomplete="off" spellcheck="false" placeholder="123456789">
      </label>
    </div>

    <p v-if="!app.telegram?.has_token" class="hint">
      Создайте бота у <a href="https://t.me/BotFather" target="_blank" rel="noopener">@BotFather</a> (/newbot),
      вставьте токен и сохраните. Затем напишите своему боту /start — chat_id появится здесь.
    </p>
    <p v-else-if="app.telegram.seen_chats.length" class="hint chats">
      Писали боту:
      <BaseButton
        v-for="c in app.telegram.seen_chats"
        :key="c.id"
        size="sm"
        @click="draft.telegram_chat_id = c.id"
      >{{ c.name }} · {{ c.id }}</BaseButton>
    </p>
    <p v-else class="hint">
      Напишите вашему боту
      <a v-if="app.telegram.bot_username" :href="`https://t.me/${app.telegram.bot_username}`" target="_blank" rel="noopener">@{{ app.telegram.bot_username }}</a>
      команду /start — chat_id появится здесь.
    </p>

    <CheckboxField
      v-model="draft.telegram_reports"
      label="Присылать плановые отчёты (после каждой проверки)"
      hint="Если выключить — придут только тревоги о новом вагоне или свободной кабинке, предупреждения об ошибках и «поезд отправился». Отчёты останутся в ленте событий."
    />
    <CheckboxField
      v-model="draft.quiet_reports"
      :disabled="!draft.telegram_reports"
      label="Плановые отчёты без звука (тревоги — всегда со звуком)"
    />
    <CheckboxField v-model="draft.telegram_commands" label="Команды бота /status, /check, /interval" />
    <div class="row test">
      <BaseButton :loading="testing" @click="test">Отправить тестовое сообщение</BaseButton>
      <span v-if="result" :class="result.ok ? 'ok' : 'bad'">{{ result.text }}</span>
    </div>
  </SettingsSection>
</template>

<style scoped>
.chats { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
.test { align-items: center; }
.ok { color: var(--good-ink); font-size: 13px; }
.bad { color: var(--crit); font-size: 13px; }
</style>
