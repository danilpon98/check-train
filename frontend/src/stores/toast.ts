import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Toast {
  id: number
  text: string
  tone: 'info' | 'error'
}

export const useToastStore = defineStore('toast', () => {
  const items = ref<Toast[]>([])
  let seq = 0

  function show(text: string, opts: { tone?: Toast['tone']; ms?: number } = {}) {
    const id = ++seq
    items.value.push({ id, text, tone: opts.tone ?? 'info' })
    if (items.value.length > 3) items.value.shift()
    setTimeout(() => dismiss(id), opts.ms ?? 3500)
  }
  const error = (e: unknown, ms = 6000) => show(e instanceof Error ? e.message : String(e), { tone: 'error', ms })
  function dismiss(id: number) {
    items.value = items.value.filter((t) => t.id !== id)
  }

  return { items, show, error, dismiss }
})
