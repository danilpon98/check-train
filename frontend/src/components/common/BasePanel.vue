<script setup lang="ts">
defineProps<{ as?: string }>()
</script>

<template>
  <component :is="as ?? 'section'" class="panel"><slot /></component>
</template>

<style scoped>
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 16px;
}
</style>
