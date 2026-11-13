<script setup lang="ts">
import { computed } from 'vue'
import type { Car } from '@/api/types'
import { buildSeatMap, seatTitle } from '@/utils/seatmap'

/**
 * Схема вагона: кабинки слева направо, в каждой сетка 2×2 (сверху верхние полки),
 * под ней — пара боковых мест плацкарта. Целиком свободная кабинка подсвечена.
 */
const props = defineProps<{ car: Car }>()
const columns = computed(() => buildSeatMap(props.car))
</script>

<template>
  <div v-if="columns.length" class="map" :aria-label="`Схема вагона ${car.number}`" role="img">
    <div v-for="col in columns" :key="col.key" class="col">
      <div class="cab" :class="{ full: col.fullyFree }">
        <i v-for="s in col.seats" :key="s.number" class="s" :class="{ f: s.free }" :title="seatTitle(s)" />
      </div>
      <div v-if="col.sides.length" class="side">
        <i v-for="s in col.sides" :key="s.number" class="s" :class="{ f: s.free }" :title="seatTitle(s)" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.map { display: flex; gap: 3px; overflow-x: auto; padding-bottom: 2px; }
.col { display: flex; flex-direction: column; }
.cab { display: grid; grid-template-columns: repeat(2, 10px); grid-auto-rows: 10px; gap: 2px; padding: 2px; border-radius: 4px; }
.cab.full { background: color-mix(in srgb, var(--good) 22%, transparent); outline: 1.5px solid var(--good); }
.side { display: grid; grid-template-columns: repeat(2, 10px); gap: 2px; padding: 0 2px; margin-top: 4px; }
.s { width: 10px; height: 10px; border-radius: 2px; background: var(--seat-taken); }
.s.f { background: var(--seat-free); }
.cab.full .s.f { background: var(--good); }
</style>
