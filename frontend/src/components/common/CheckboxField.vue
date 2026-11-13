<script setup lang="ts">
/**
 * Чекбокс в едином стиле приложения: свой квадрат с галочкой вместо системного.
 * Нативный <input> остаётся (доступность, клавиатура, формы) — меняется только внешний вид.
 * Подпись выровнена по центру квадрата; необязательная подсказка — под подписью.
 */
defineProps<{ label: string; hint?: string; disabled?: boolean }>()
const model = defineModel<boolean>({ required: true })
</script>

<template>
  <label class="cb" :class="{ disabled }">
    <input v-model="model" type="checkbox" :disabled="disabled">
    <span class="text">
      <span class="label">{{ label }}</span>
      <span v-if="hint" class="hint">{{ hint }}</span>
    </span>
  </label>
</template>

<style scoped>
.cb { display: flex; align-items: flex-start; gap: 10px; cursor: pointer; user-select: none; -webkit-tap-highlight-color: transparent; }
.cb.disabled { cursor: not-allowed; opacity: .55; }

input {
  appearance: none; -webkit-appearance: none; margin: 0; flex: none;
  width: 20px; height: 20px; border-radius: 6px; cursor: inherit;
  border: 1.5px solid color-mix(in srgb, var(--muted) 70%, transparent);
  background: var(--surface) center / 14px 14px no-repeat;
  transition: background-color .15s, border-color .15s, box-shadow .15s, transform .1s;
}
.cb:not(.disabled):hover input { border-color: var(--accent); }
.cb:not(.disabled):active input { transform: scale(.92); }
input:checked {
  background-color: var(--accent); border-color: var(--accent);
  /* белая галочка */
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='white' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3.5 8.5l3 3 6-7'/%3E%3C/svg%3E");
}
input:focus-visible { outline: none; box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 25%, transparent); }

.text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
/* подпись по центру квадрата 20px: строка 20px */
.label { line-height: 20px; color: var(--text); }
.hint { color: var(--muted); font-size: 12px; line-height: 1.4; }

@media (prefers-reduced-motion: reduce) { input { transition: none; } }
</style>
