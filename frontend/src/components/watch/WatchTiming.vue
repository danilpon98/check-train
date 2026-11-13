<script setup lang="ts">
import { computed } from 'vue'
import type { Watch } from '@/api/types'
import { useNow } from '@/composables/useNow'
import { ago, duration, fmtDateTime } from '@/utils/format'

/** Когда проверяли, когда проверим снова, прогресс до следующей проверки, ошибки. */
const props = defineProps<{ watch: Watch }>()
const now = useNow()

const next = computed(() => {
  const w = props.watch
  if (!w.next_check_at) return null
  const nextT = new Date(w.next_check_at).getTime()
  const fromT = w.last_check_at ? new Date(w.last_check_at).getTime() : null
  const left = (nextT - now.value) / 1000
  const progress = fromT ? Math.min(100, Math.max(0, ((now.value - fromT) / (nextT - fromT)) * 100)) : 0
  return { text: left > 0 ? duration(left) : 'сейчас…', progress }
})
</script>

<template>
  <div class="timing">
    <span>Проверено: <b>{{ ago(watch.last_check_at, now) }}</b></span>
    <template v-if="next">
      <span>Следующая через <b class="num">{{ next.text }}</b></span>
      <div class="progress" role="progressbar" :aria-valuenow="Math.round(next.progress)" aria-valuemin="0" aria-valuemax="100">
        <i :style="{ transform: `scaleX(${next.progress / 100})` }" />
      </div>
    </template>
    <span v-if="watch.started_at" class="hint">отслеживается с {{ fmtDateTime(watch.started_at) }}</span>
  </div>
  <div v-if="watch.consecutive_failures" class="err">
    ⚠ Ошибок подряд: {{ watch.consecutive_failures }}. {{ watch.last_error }} — повторю автоматически.
  </div>
  <div v-if="watch.pending_empty" class="err">
    Сайт ответил «ничего не найдено» — перепроверяю, прежде чем поверить.
  </div>
</template>

<style scoped>
.timing { margin: 14px 0 4px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; color: var(--text-2); font-size: 13px; }
.progress { flex: 1; min-width: 120px; height: 4px; background: var(--surface-2); border-radius: 4px; overflow: hidden; }
/* transform вместо width: анимация на GPU, без пересчёта раскладки страницы каждый кадр */
.progress i {
  display: block; width: 100%; height: 100%; background: var(--accent); border-radius: 4px;
  transform-origin: left center; transition: transform 1s linear; will-change: transform;
}
.err { margin-top: 8px; padding: 8px 12px; border-radius: 10px; background: var(--crit-soft); color: var(--text); font-size: 13px; }
</style>
