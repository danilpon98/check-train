<script setup lang="ts">
import type { WatchTotals } from '@/api/types'
import { plural } from '@/utils/format'
import KpiTile from './KpiTile.vue'

defineProps<{ totals: WatchTotals }>()
</script>

<template>
  <div class="kpis">
    <KpiTile :value="totals.free" :label="plural(totals.free, 'свободное место', 'свободных места', 'свободных мест')" />
    <KpiTile :value="totals.cars" :label="`${plural(totals.cars, 'вагон', 'вагона', 'вагонов')} с местами`" />
    <KpiTile
      :value="totals.cabins"
      :hot="totals.cabins > 0"
      :label="`${plural(totals.cabins, 'свободная кабинка', 'свободные кабинки', 'свободных кабинок')} (4 места)`"
    />
    <KpiTile
      :value="totals.new_cars"
      :hot="totals.new_cars > 0"
      :label="`${plural(totals.new_cars, 'новый вагон', 'новых вагона', 'новых вагонов')} · всего известно ${totals.known}`"
    />
  </div>
</template>

<style scoped>
.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 14px 0; }
@media (max-width: 640px) { .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
