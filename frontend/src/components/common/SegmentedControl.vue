<script setup lang="ts" generic="T extends string | number">
defineProps<{ options: readonly { value: T; label: string }[]; label?: string }>()
const model = defineModel<T>({ required: true })
</script>

<template>
  <div class="seg" role="radiogroup" :aria-label="label">
    <button
      v-for="o in options"
      :key="String(o.value)"
      type="button"
      role="radio"
      :aria-checked="model === o.value"
      :class="{ on: model === o.value }"
      @click="model = o.value"
    >{{ o.label }}</button>
  </div>
</template>

<style scoped>
.seg { display: inline-flex; background: var(--surface-2); border-radius: 9px; padding: 2px; }
button {
  border: 0; background: transparent; padding: 4px 10px; border-radius: 7px;
  cursor: pointer; font-size: 12px; color: var(--text-2);
}
button.on { background: var(--surface); color: var(--text); box-shadow: 0 1px 2px rgba(0, 0, 0, .08); }
button:focus-visible { outline: 2px solid var(--accent); }
</style>
