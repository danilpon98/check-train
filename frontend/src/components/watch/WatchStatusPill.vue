<script setup lang="ts">
import type { WatchStatus } from '@/api/types'

defineProps<{ status: WatchStatus }>()

const LABELS: Record<WatchStatus, string> = {
  ok: '● Работает',
  error: '⚠ Ошибки проверки',
  paused: '⏸ На паузе',
  finished: '🏁 Поезд ушёл',
  checking: '⟳ Проверяю…',
  starting: '… Первая проверка',
}
</script>

<template>
  <span class="pill" :class="status">{{ LABELS[status] ?? status }}</span>
</template>

<style scoped>
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.ok { background: var(--good-soft); color: var(--good-ink); }
.error { background: var(--crit-soft); color: var(--crit); }
.paused, .finished { background: var(--surface-2); color: var(--text-2); }
.checking, .starting { background: var(--accent-soft); color: var(--accent-ink); }
</style>
