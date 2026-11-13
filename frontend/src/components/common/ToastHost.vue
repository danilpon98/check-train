<script setup lang="ts">
import { useToastStore } from '@/stores/toast'

const toasts = useToastStore()
</script>

<template>
  <div class="host" role="status" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="t in toasts.items" :key="t.id" class="toast" :class="t.tone" @click="toasts.dismiss(t.id)">
        {{ t.text }}
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.host {
  position: fixed; left: 50%; bottom: 20px; transform: translateX(-50%); z-index: 200;
  display: flex; flex-direction: column; gap: 8px; align-items: center; width: max-content; max-width: calc(100vw - 32px);
}
.toast {
  background: var(--text); color: var(--bg); padding: 10px 16px; border-radius: 10px; cursor: pointer;
  box-shadow: 0 6px 20px rgba(0, 0, 0, .2);
}
.toast.error { background: var(--crit); color: #fff; }
.toast-enter-active, .toast-leave-active { transition: opacity .2s, transform .2s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(12px); }
</style>
