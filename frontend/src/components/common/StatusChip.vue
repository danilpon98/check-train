<script setup lang="ts">
/** Маленький чип со статусной точкой: ok / warn / bad / neutral. */
withDefaults(defineProps<{ tone?: 'ok' | 'warn' | 'bad' | 'neutral' | 'accent'; title?: string; clickable?: boolean }>(), {
  tone: 'neutral',
})
defineEmits<{ click: [] }>()
</script>

<template>
  <component
    :is="clickable ? 'button' : 'span'"
    :type="clickable ? 'button' : undefined"
    class="chip"
    :class="tone"
    :title="title"
    @click="$emit('click')"
  >
    <span class="dot" aria-hidden="true" />
    <slot />
  </component>
</template>

<style scoped>
.chip {
  display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px;
  font-size: 12px; background: var(--surface-2); color: var(--text-2); border: 1px solid var(--border);
  white-space: nowrap;
}
button.chip { cursor: pointer; }
button.chip:hover { border-color: var(--muted); }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted); }
.ok .dot { background: var(--good); }
.warn .dot { background: var(--warn); }
.bad .dot { background: var(--crit); }
.accent .dot { background: var(--accent); }
</style>
