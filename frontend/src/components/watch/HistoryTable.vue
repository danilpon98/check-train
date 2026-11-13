<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import BaseButton from '@/components/common/BaseButton.vue'
import { useCheckLog } from '@/composables/useCheckLog'
import { useLoadMoreOnVisible } from '@/composables/useLoadMoreOnVisible'
import { fmtDateTime } from '@/utils/format'

/**
 * Журнал проверок. Данные не грузятся, пока таблица свёрнута; дальше — страницами по 20
 * при прокрутке внутри таблицы. Размер DOM и трафика не зависит от длины истории.
 */
const props = defineProps<{ watchId: string; lastCheckAt: string | null }>()

const open = ref(false)
const log = useCheckLog(toRef(() => props.watchId), toRef(() => props.lastCheckAt), open)

const scroller = ref<HTMLElement | null>(null)
const sentinel = ref<HTMLElement | null>(null)
const canLoad = computed(() => log.hasMore.value && !log.loading.value && !log.error.value)
useLoadMoreOnVisible(sentinel, scroller, { enabled: open, canLoad, load: log.loadMore, marginPx: 80 })

const COLS = 5
</script>

<template>
  <details @toggle="open = ($event.target as HTMLDetailsElement).open">
    <summary class="hint">Последние проверки (таблица)</summary>

    <p v-if="!log.loaded.value && log.loading.value" class="hint pad">Загрузка…</p>
    <p v-else-if="log.loaded.value && !log.rows.value.length" class="hint pad">Проверок ещё не было.</p>

    <!-- высота ограничена: своя прокрутка, заголовок закреплён, строки догружаются при прокрутке -->
    <div v-if="log.rows.value.length" ref="scroller" class="scroll" tabindex="0" aria-label="Журнал проверок">
      <table>
        <thead>
          <tr><th>Время</th><th>Свободно</th><th>Вагонов</th><th>Кабинок</th><th>Итог</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in log.rows.value" :key="r.id" :class="{ fail: !r.ok }">
            <td>{{ fmtDateTime(r.at) }}</td>
            <td>{{ r.total_free ?? '—' }}</td>
            <td>{{ r.cars ?? '—' }}</td>
            <td>{{ r.cabins ?? '—' }}</td>
            <td>{{ r.ok ? 'ок' : (r.error || 'ошибка') }}</td>
          </tr>
          <tr ref="sentinel" class="sentinel" aria-hidden="true"><td :colspan="COLS" /></tr>
          <tr v-if="log.loading.value" class="note"><td :colspan="COLS">Загрузка…</td></tr>
          <tr v-else-if="!log.hasMore.value" class="note"><td :colspan="COLS">Это все проверки (хранятся 30 дней)</td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="log.error.value" class="error" role="alert">
      Не удалось загрузить журнал: {{ log.error.value }}
      <BaseButton size="sm" @click="log.rows.value.length ? log.loadMore() : log.loadFirst()">Повторить</BaseButton>
    </div>
  </details>
</template>

<style scoped>
summary { cursor: pointer; padding: 4px 0; }
.pad { padding: 6px 0; }
.scroll {
  max-height: 240px; overflow-y: auto; overscroll-behavior: contain; margin-top: 6px;
  border: 1px solid var(--border); border-radius: 10px;
}
.scroll:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
table { width: 100%; font-size: 12px; border-collapse: collapse; }
th {
  position: sticky; top: 0; z-index: 1; background: var(--surface-2);
  text-align: left; color: var(--text-2); font-weight: 600;
}
td, th { padding: 5px 8px; border-bottom: 1px solid var(--border); }
tr.fail td { color: var(--crit); }
tr.sentinel td { padding: 0; border: 0; height: 1px; }
tr.note td { color: var(--muted); text-align: center; border-bottom: 0; padding: 8px; }
.error {
  display: flex; gap: 8px; align-items: center; justify-content: space-between; flex-wrap: wrap;
  margin-top: 6px; padding: 8px 12px; border-radius: 10px; background: var(--crit-soft); font-size: 13px;
}
</style>
