<script setup lang="ts">
import type { WatchPreview } from '@/api/types'
import { carsIn, fmtKZ, seats } from '@/utils/format'

defineProps<{ preview: WatchPreview }>()
</script>

<template>
  <div class="preview">
    <div v-if="preview.exists" class="bad">Этот поезд уже отслеживается</div>
    <div v-else class="ok">✓ Ссылка работает</div>
    <div><b>{{ preview.train }}</b> {{ preview.route }}</div>
    <div v-if="preview.departure_text || preview.departure">
      Отправление: {{ preview.departure_text ?? fmtKZ(preview.departure!) }}
    </div>
    <div v-if="preview.status === 'empty'">
      Сейчас мест нет (или продажа ещё не открыта) — это нормально, сервис дождётся появления.
    </div>
    <div v-else>
      Сейчас: {{ seats(preview.totals.free) }} в {{ carsIn(preview.totals.cars) }}
      ({{ preview.cars.map((c) => c.number).join(', ') }}), свободных кабинок: {{ preview.totals.cabins }}
    </div>
  </div>
</template>

<style scoped>
.preview { background: var(--surface-2); border-radius: 12px; padding: 12px; font-size: 13px; display: grid; gap: 2px; }
.ok { color: var(--good-ink); font-weight: 600; }
.bad { color: var(--crit); font-weight: 600; }
</style>
