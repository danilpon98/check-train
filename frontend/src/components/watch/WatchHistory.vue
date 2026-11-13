<script setup lang="ts">
import { computed, toRef } from 'vue'
import type { Watch } from '@/api/types'
import SegmentedControl from '@/components/common/SegmentedControl.vue'
import { useWatchHistory } from '@/composables/useWatchHistory'
import { usePrefsStore } from '@/stores/prefs'
import HistoryChart from './HistoryChart.vue'
import HistoryTable from './HistoryTable.vue'

const props = defineProps<{ watch: Watch }>()
const prefs = usePrefsStore()

const RANGES = [
  { value: 24, label: '24 ч' },
  { value: 72, label: '3 дня' },
  { value: 168, label: 'неделя' },
  { value: 0, label: 'всё' },
] as const

const hours = computed<number>({
  get: () => prefs.rangeFor(props.watch.id),
  set: (v) => prefs.setRange(props.watch.id, v),
})
const { rows, error } = useWatchHistory(
  toRef(() => props.watch.id),
  hours,
  toRef(() => props.watch.last_check_at),
)
</script>

<template>
  <div class="head">
    <h3 class="section-title">Свободные места во времени</h3>
    <SegmentedControl v-model="hours" :options="RANGES" label="Период графика" />
  </div>
  <p v-if="error" class="hint warn">Не удалось загрузить историю: {{ error }}</p>
  <HistoryChart v-else :rows="rows" :hours="hours" />
  <HistoryTable :watch-id="watch.id" :last-check-at="watch.last_check_at" />
</template>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; margin: 18px 0 6px; }
.head .section-title { margin: 0; }
</style>
