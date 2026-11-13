<script setup lang="ts">
import { computed } from 'vue'
import type { Car } from '@/api/types'
import { cabinLabel, fmtDateTime, plural, seatsWord } from '@/utils/format'
import SeatMap from './SeatMap.vue'

const props = defineProps<{ car: Car }>()
const cabins = computed(() => props.car.free_cabins.length)
</script>

<template>
  <article class="car" :class="{ 'has-cabin': cabins, 'is-new': car.is_new }">
    <div class="top">
      <div>
        <div class="no">
          Вагон {{ car.number }}
          <span v-if="car.is_new" class="tag new">НОВЫЙ</span>
          <span v-if="cabins" class="tag cab">{{ cabins }} {{ plural(cabins, 'кабинка', 'кабинки', 'кабинок') }}</span>
        </div>
        <div class="type">{{ car.car_type }} {{ car.service_class }}</div>
      </div>
      <div class="free">{{ car.free_seats }}<small>{{ seatsWord(car.free_seats) }}</small></div>
    </div>
    <SeatMap :car="car" />
    <div v-if="cabins" class="cabins">
      Кабинки целиком:
      <template v-for="(c, i) in car.free_cabins" :key="c.seats.join()">{{ i ? ', ' : '' }}{{ cabinLabel(c.seats) }}{{ c.for_disabled ? ' ♿' : '' }}</template>
    </div>
    <div class="meta">
      <span>{{ car.price }}</span>
      <span v-if="car.is_new && car.first_seen">появился {{ fmtDateTime(car.first_seen) }}</span>
    </div>
  </article>
</template>

<style scoped>
.car {
  border: 1px solid var(--border); border-radius: 12px; padding: 10px 12px; background: var(--surface);
  display: flex; flex-direction: column; gap: 8px; min-width: 0;
}
.car.has-cabin { border-color: var(--good); box-shadow: 0 0 0 2px color-mix(in srgb, var(--good) 35%, transparent); }
.car.is-new { border-color: var(--accent); }
.top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.no { font-weight: 700; font-size: 16px; }
.type { color: var(--text-2); font-size: 12px; }
.free { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; line-height: 1; }
.free small { display: block; font-size: 11px; font-weight: 400; color: var(--muted); }
.tag { display: inline-block; font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 6px; margin-left: 6px; vertical-align: middle; color: #fff; }
.tag.new { background: var(--accent); }
.tag.cab { background: var(--good); }
.cabins { font-size: 12px; color: var(--good-ink); font-weight: 600; }
.meta { display: flex; justify-content: space-between; color: var(--text-2); font-size: 12px; gap: 8px; flex-wrap: wrap; }
</style>
