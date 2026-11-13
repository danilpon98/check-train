<script setup lang="ts">
import { computed } from 'vue'
import type { EventKind, FeedEvent } from '@/api/types'
import { fmtDateTime, stripLeadingEmoji } from '@/utils/format'

const props = defineProps<{ event: FeedEvent; highlight?: boolean }>()

const ICONS: Record<EventKind, string> = {
  alert: '🚨', report: '📋', error: '⚠️', recovered: '✅', finished: '🏁', info: 'ℹ️',
}
const title = computed(() => stripLeadingEmoji(props.event.title))
const fullText = computed(() => {
  const t = props.event.data?.text
  return t && t !== props.event.body ? t : null
})
</script>

<template>
  <li class="item" :class="[event.kind, { flash: highlight }]">
    <span class="ico" aria-hidden="true">{{ ICONS[event.kind] ?? '•' }}</span>
    <div>
      <div class="t">{{ title }}</div>
      <div class="b">{{ event.body }}</div>
      <div class="w">
        {{ fmtDateTime(event.at) }}
        <template v-if="event.url"> · <a :href="event.url" target="_blank" rel="noopener">сайт</a></template>
      </div>
      <details v-if="fullText">
        <summary>Полный текст</summary>
        <pre>{{ fullText }}</pre>
      </details>
    </div>
  </li>
</template>

<style scoped>
.item { padding: 10px 4px; border-bottom: 1px solid var(--border); display: grid; grid-template-columns: 24px 1fr; gap: 8px; }
.item:last-child { border-bottom: 0; }
.ico { font-size: 16px; line-height: 1.3; }
.t { font-weight: 600; font-size: 13px; }
.b { color: var(--text-2); font-size: 13px; white-space: pre-line; }
.w { color: var(--muted); font-size: 11px; }
.alert { background: var(--good-soft); border-radius: 10px; border-bottom-color: transparent; margin: 4px 0; padding: 10px 8px; }
.error { background: var(--crit-soft); border-radius: 10px; border-bottom-color: transparent; margin: 4px 0; padding: 10px 8px; }
.flash { animation: flash 1.5s ease 2; }
@keyframes flash { 50% { background: var(--accent-soft); } }
summary { cursor: pointer; color: var(--accent-ink); font-size: 12px; margin-top: 4px; }
pre { white-space: pre-wrap; font: 12px/1.45 system-ui, sans-serif; color: var(--text-2); margin: 6px 0 0; }
</style>
