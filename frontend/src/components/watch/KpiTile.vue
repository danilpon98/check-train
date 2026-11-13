<script setup lang="ts">
/** Плитка с крупным числом. hot — подсветка, когда значение означает находку. */
defineProps<{ value: number; label: string; hot?: boolean }>()
</script>

<template>
  <div class="kpi" :class="{ hot }">
    <div class="v">{{ value }}</div>
    <div class="l">{{ label }}</div>
  </div>
</template>

<style scoped>
.kpi { background: var(--surface-2); border-radius: 12px; padding: 10px 12px; }
.v { font-size: 26px; font-weight: 700; font-variant-numeric: tabular-nums; }
.l { color: var(--text-2); font-size: 12px; }
.hot { background: var(--good-soft); outline: 2px solid var(--good); }
.hot .v { color: var(--good-ink); }
</style>
