<script setup lang="ts">
import { computed } from 'vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BasePanel from '@/components/common/BasePanel.vue'
import { useAppStore } from '@/stores/app'
import { usePrefsStore } from '@/stores/prefs'
import { usePushStore } from '@/stores/push'

/** Что ещё нужно сделать, чтобы не пропустить находку. Скрывается, когда всё готово. */
const emit = defineEmits<{ add: []; openSettings: [] }>()
const app = useAppStore()
const push = usePushStore()
const prefs = usePrefsStore()
const port = location.port

const hasWatches = computed(() => app.watches.length > 0)
const pushOn = computed(() => push.state === 'on')
const tgOk = computed(() => !!app.telegram?.configured && app.telegram.enabled && !app.telegram.last_error)
const visible = computed(() => !hasWatches.value || !pushOn.value || (!tgOk.value && !prefs.skipTelegram))
</script>

<template>
  <BasePanel v-if="app.state && visible" class="setup">
    <h2>Настройка уведомлений</h2>
    <ul>
      <li :class="{ done: hasWatches }">
        <span>{{ hasWatches ? '✅' : '⬜' }} Добавьте поезд для отслеживания</span>
        <BaseButton v-if="!hasWatches" size="sm" variant="primary" @click="emit('add')">＋ Добавить поезд</BaseButton>
      </li>
      <li :class="{ done: pushOn }">
        <span>{{ pushOn ? '✅' : '⬜' }} Push-уведомления в этом браузере</span>
        <BaseButton v-if="push.state === 'off'" size="sm" variant="primary" :loading="push.busy" @click="push.enable()">Включить</BaseButton>
        <span v-else-if="push.state === 'denied'" class="hint">Разрешите уведомления для этого сайта (значок замка в адресной строке)</span>
        <span v-else-if="push.state === 'insecure'" class="hint">
          Откройте <a :href="`http://localhost:${port}/`">http://localhost:{{ port }}</a> — push работает только на localhost или HTTPS
        </span>
        <span v-else-if="push.state === 'unsupported'" class="hint">Браузер не поддерживает Web Push</span>
      </li>
      <li v-if="!prefs.skipTelegram || tgOk" :class="{ done: tgOk }">
        <span>{{ tgOk ? '✅' : '⬜' }} Telegram (необязательно)</span>
        <span v-if="!tgOk" class="btns">
          <BaseButton size="sm" @click="emit('openSettings')">Настроить</BaseButton>
          <BaseButton size="sm" variant="ghost" @click="prefs.skipTelegram = true">Не нужно</BaseButton>
        </span>
      </li>
    </ul>
  </BasePanel>
</template>

<style scoped>
.setup { margin-bottom: 20px; }
h2 { margin-bottom: 10px; }
ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
li {
  display: flex; gap: 10px; align-items: center; justify-content: space-between; flex-wrap: wrap;
  padding: 10px 12px; border-radius: 10px; background: var(--surface-2);
}
li.done { opacity: .7; }
.btns { display: flex; gap: 4px; }
</style>
