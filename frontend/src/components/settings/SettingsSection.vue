<script setup lang="ts">
defineProps<{ title: string }>()
</script>

<template>
  <fieldset class="section">
    <legend>{{ title }}</legend>
    <slot />
  </fieldset>
</template>

<style scoped>
.section { border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; margin: 0; }
legend { padding: 0 6px; font-weight: 600; }
</style>
