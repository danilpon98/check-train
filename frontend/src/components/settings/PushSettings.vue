<script setup lang="ts">
import { storeToRefs } from 'pinia'
import BaseButton from '@/components/common/BaseButton.vue'
import CheckboxField from '@/components/common/CheckboxField.vue'
import { playSiren, unlockAudio } from '@/composables/useSiren'
import { TEST_ALARM, useAlarmStore } from '@/stores/alarm'
import { useAppStore } from '@/stores/app'
import { usePrefsStore } from '@/stores/prefs'
import { usePushStore } from '@/stores/push'
import { useSettingsStore } from '@/stores/settings'
import SettingsSection from './SettingsSection.vue'

const emit = defineEmits<{ close: [] }>()
const { draft } = storeToRefs(useSettingsStore())
const push = usePushStore()
const app = useAppStore()
const prefs = usePrefsStore()
const alarm = useAlarmStore()
const port = location.port

function toggleSound(v: boolean) {
  prefs.sound = v
  if (v) { unlockAudio(); playSiren() }
}

function testAlarm() {
  unlockAudio()
  emit('close')
  alarm.show({ ...TEST_ALARM, at: new Date().toISOString() })
}
</script>

<template>
  <SettingsSection v-if="draft" title="Уведомления в браузере (Web Push)">
    <p class="state">
      <template v-if="push.state === 'on'">✅ Включены в этом браузере. Приходят, даже если вкладка закрыта (браузер должен быть запущен).</template>
      <template v-else-if="push.state === 'off'">Выключены в этом браузере.</template>
      <template v-else-if="push.state === 'denied'">⛔ Браузер запретил уведомления для этого сайта — разрешите их через значок замка в адресной строке.</template>
      <template v-else-if="push.state === 'insecure'">
        ⚠ Страница открыта не через localhost. Push работает только на
        <a :href="`http://localhost:${port}/`">http://localhost:{{ port }}</a> или по HTTPS.
      </template>
      <template v-else>Этот браузер не поддерживает Web Push.</template>
      <span class="hint"> Подписанных браузеров: {{ app.push?.subscriptions ?? 0 }}.</span>
    </p>
    <div class="row">
      <BaseButton v-if="push.state === 'off'" variant="primary" :loading="push.busy" @click="push.enable()">Включить уведомления</BaseButton>
      <template v-if="push.state === 'on'">
        <BaseButton @click="push.test('alert')">Тестовый push</BaseButton>
        <BaseButton variant="ghost" :loading="push.busy" @click="push.disable()">Выключить</BaseButton>
      </template>
    </div>
    <CheckboxField v-model="draft.push_reports" label="Присылать в браузер и плановые отчёты (тревоги и ошибки — всегда)" />
    <CheckboxField :model-value="prefs.sound" label="Звук тревоги в открытой вкладке" @update:model-value="toggleSound" />
    <div><BaseButton @click="testAlarm">Показать тестовую тревогу на странице</BaseButton></div>
  </SettingsSection>
</template>

<style scoped>
.state { margin: 0; }
</style>
