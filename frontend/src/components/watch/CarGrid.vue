<script setup lang="ts">
import type { Watch } from '@/api/types'
import AbsentCarTile from './AbsentCarTile.vue'
import CarTile from './CarTile.vue'
import SeatLegend from './SeatLegend.vue'

defineProps<{ watch: Watch }>()
</script>

<template>
  <template v-if="watch.cars.length || watch.absent_known.length">
    <h3 class="section-title">Вагоны</h3>
    <div class="grid">
      <CarTile v-for="c in watch.cars" :key="c.number" :car="c" />
      <AbsentCarTile v-for="a in watch.absent_known" :key="`absent-${a.number}`" :car="a" />
    </div>
    <SeatLegend />
  </template>
  <p v-else class="hint">
    {{ watch.status === 'starting' ? 'Жду первую проверку…' : 'Свободных мест в поезде нет (или продажа ещё не открыта).' }}
  </p>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(260px, 100%), 1fr)); gap: 10px; }
</style>
