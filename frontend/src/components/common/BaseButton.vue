<script setup lang="ts">
/** Кнопка или ссылка-кнопка (если передан href). */
withDefaults(defineProps<{
  variant?: 'default' | 'primary' | 'ghost' | 'buy' | 'danger'
  size?: 'md' | 'sm' | 'lg'
  href?: string
  loading?: boolean
  disabled?: boolean
  icon?: boolean
  type?: 'button' | 'submit'
}>(), { variant: 'default', size: 'md', type: 'button' })
</script>

<template>
  <a
    v-if="href"
    :href="href"
    target="_blank"
    rel="noopener"
    class="btn"
    :class="[variant, size, { icon }]"
  ><slot /></a>
  <button
    v-else
    :type="type"
    class="btn"
    :class="[variant, size, { icon }]"
    :disabled="disabled || loading"
  >
    <span v-if="loading" class="spin" aria-hidden="true">⟳</span>
    <slot />
  </button>
</template>

<style scoped>
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  min-height: 34px; padding: 6px 14px; border-radius: 10px; cursor: pointer;
  background: var(--surface); border: 1px solid var(--border); color: var(--text);
  text-decoration: none; font-weight: 500; white-space: nowrap;
  transition: background .15s, border-color .15s, filter .15s;
}
.btn:hover { background: var(--surface-2); }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.sm { min-height: 28px; padding: 3px 10px; font-size: 13px; border-radius: 8px; }
.lg { min-height: 44px; padding: 10px 22px; font-size: 16px; }
.icon { width: 36px; padding: 0; font-size: 18px; }
.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.primary:hover { background: var(--accent-ink); }
.ghost { background: transparent; border-color: transparent; color: var(--text-2); }
.buy { background: var(--good); border-color: var(--good); color: #fff; font-weight: 700; }
.buy:hover { background: var(--good); filter: brightness(1.08); }
.danger:hover { color: var(--crit); border-color: var(--crit); }
</style>
