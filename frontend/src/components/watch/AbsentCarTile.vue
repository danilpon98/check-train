<script setup lang="ts">
import type { AbsentCar } from '@/api/types'

/** Известный вагон, в котором сейчас нет мест (сайт его не показывает). */
defineProps<{ car: AbsentCar }>()
</script>

<template>
  <article class="car">
    <div class="top">
      <span class="no">Вагон {{ car.number }}<span v-if="car.is_new" class="tag">НОВЫЙ</span></span>
      <span class="type">мест нет</span>
    </div>
    <div class="meta">был в продаже, сейчас распродан</div>
  </article>
</template>

<style scoped>
.car { border: 1px dashed var(--border); border-radius: 12px; padding: 10px 12px; opacity: .6; min-width: 0; }
.top { display: flex; justify-content: space-between; align-items: baseline; }
.no { font-weight: 700; font-size: 16px; }
.type, .meta { color: var(--text-2); font-size: 12px; }
.tag { font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 6px; margin-left: 6px; background: var(--accent); color: #fff; }
</style>
