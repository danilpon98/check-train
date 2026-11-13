<script setup lang="ts">
import { ref, watch } from 'vue'

/** Модальное окно на нативном <dialog>: фокус, Esc и затемнение фона — средствами браузера. */
withDefaults(defineProps<{ title: string; wide?: boolean }>(), { wide: false })
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ submit: [] }>()
const el = ref<HTMLDialogElement | null>(null)

watch([open, el], ([v, d]) => {
  if (!d) return
  if (v && !d.open) d.showModal()
  if (!v && d.open) d.close()
}, { flush: 'post', immediate: true })
</script>

<template>
  <dialog ref="el" class="dlg" :class="{ wide }" @close="open = false">
    <form class="body" method="dialog" @submit.prevent="emit('submit')">
      <h2>{{ title }}</h2>
      <slot />
      <div class="actions">
        <slot name="actions" />
      </div>
    </form>
  </dialog>
</template>

<style scoped>
.dlg {
  border: 0; border-radius: 16px; padding: 0; width: min(560px, calc(100vw - 32px));
  background: var(--surface); color: var(--text); box-shadow: 0 20px 60px rgba(0, 0, 0, .3);
}
.dlg.wide { width: min(720px, calc(100vw - 32px)); }
.dlg::backdrop { background: rgba(0, 0, 0, .4); }
.body { padding: 20px; display: flex; flex-direction: column; gap: 12px; max-height: calc(100vh - 48px); overflow-y: auto; }
.actions {
  display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap;
  position: sticky; bottom: -20px; background: var(--surface); padding: 10px 0 0;
}
</style>
