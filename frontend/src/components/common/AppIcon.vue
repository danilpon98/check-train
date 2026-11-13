<script setup lang="ts">
/**
 * Контурные иконки (stroke = currentColor): берут цвет текста кнопки, одинаково
 * хорошо видны в светлой и тёмной теме — в отличие от символов ✎ и 🗑 из шрифта.
 */
const props = withDefaults(defineProps<{ name: 'pencil' | 'trash'; size?: number }>(), { size: 16 })

const PATHS: Record<typeof props.name, string[]> = {
  pencil: ['M12 20h9', 'M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z'],
  trash: ['M3 6h18', 'M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2', 'M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6', 'M10 11v6', 'M14 11v6'],
}
</script>

<template>
  <svg
    class="icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="d in PATHS[name]" :key="d" :d="d" />
  </svg>
</template>

<style scoped>
.icon { flex-shrink: 0; }
</style>
