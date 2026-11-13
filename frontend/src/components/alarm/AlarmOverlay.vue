<script setup lang="ts">
import { onKeyStroke } from '@vueuse/core'
import BaseButton from '@/components/common/BaseButton.vue'
import { useAlarmStore } from '@/stores/alarm'

/** Полноэкранная тревога о находке: мигающий фон, крупный текст, кнопка «Купить». */
const alarm = useAlarmStore()
onKeyStroke('Escape', () => { if (alarm.current) alarm.hide() })
</script>

<template>
  <Teleport to="body">
    <div v-if="alarm.current" class="alarm" role="alertdialog" aria-live="assertive" aria-modal="true">
      <div class="box">
        <div class="siren" aria-hidden="true">🚨🚨🚨</div>
        <h2>{{ alarm.current.title }}</h2>
        <div class="sub">{{ alarm.current.subtitle }}</div>
        <pre class="body">{{ alarm.current.body }}</pre>
        <div class="actions">
          <BaseButton v-if="alarm.current.url" variant="buy" size="lg" :href="alarm.current.url">🎫 Купить на сайте</BaseButton>
          <BaseButton size="lg" @click="alarm.hide()">Понятно</BaseButton>
        </div>
        <div v-if="alarm.soundNote" class="note">{{ alarm.soundNote }}</div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.alarm {
  position: fixed; inset: 0; z-index: 100; display: grid; place-items: center; padding: 16px;
  background: rgba(10, 60, 10, .55); backdrop-filter: blur(3px);
  animation: blink 1s steps(2) infinite;
}
@keyframes blink { 50% { background: rgba(160, 20, 20, .55); } }
@media (prefers-reduced-motion: reduce) { .alarm { animation: none; } }
.box {
  background: var(--surface); color: var(--text); border-radius: 18px; padding: 24px; max-width: 560px; width: 100%;
  border: 4px solid var(--good); box-shadow: 0 20px 80px rgba(0, 0, 0, .45); text-align: center;
}
.siren { font-size: 40px; letter-spacing: 6px; }
h2 { font-size: 26px; color: var(--good-ink); margin: 6px 0 4px; }
.sub { color: var(--text-2); }
.body {
  text-align: left; white-space: pre-wrap; font: 600 16px/1.5 system-ui, sans-serif; background: var(--good-soft);
  padding: 12px 14px; border-radius: 12px; margin: 14px 0;
}
.actions { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
.note { color: var(--muted); font-size: 12px; margin-top: 10px; }
</style>
