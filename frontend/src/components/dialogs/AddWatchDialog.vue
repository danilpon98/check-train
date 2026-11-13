<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '@/api/endpoints'
import type { WatchPreview } from '@/api/types'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseDialog from '@/components/common/BaseDialog.vue'
import { useAppStore } from '@/stores/app'
import WatchPreviewCard from './WatchPreviewCard.vue'

/** Добавление поезда: сначала ссылка проверяется на сайте, потом добавляется. */
const open = defineModel<boolean>('open', { required: true })
const app = useAppStore()

const url = ref('')
const name = ref('')
const preview = ref<WatchPreview | null>(null)
const error = ref('')
const checking = ref(false)
const adding = ref(false)

const canAdd = computed(() => !!preview.value && !preview.value.exists && !adding.value)

watch(open, (v) => {
  if (v) { url.value = ''; name.value = ''; preview.value = null; error.value = '' }
})
watch(url, () => { preview.value = null; error.value = '' })

async function check() {
  checking.value = true
  error.value = ''
  preview.value = null
  try {
    preview.value = await api.previewWatch(url.value, name.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    checking.value = false
  }
}

async function add() {
  if (!canAdd.value) return
  adding.value = true
  try {
    const res = await app.add(url.value, name.value)
    if (res) open.value = false
  } finally {
    adding.value = false
  }
}
</script>

<template>
  <BaseDialog v-model:open="open" title="Добавить поезд" @submit="add">
    <ol class="howto">
      <li>Найдите поезд на <a href="https://bilet.railways.kz" target="_blank" rel="noopener">bilet.railways.kz</a> и нажмите «Выбрать вагон».</li>
      <li>Скопируйте адрес страницы со списком вагонов и вставьте сюда.</li>
    </ol>
    <label class="field">Ссылка на страницу выбора вагона
      <textarea v-model.trim="url" rows="3" required placeholder="https://bilet.railways.kz/sale/default/car/search?…" />
    </label>
    <label class="field">Название (необязательно)
      <input v-model="name" maxlength="120" placeholder="Например: К маме, 27 ноября">
    </label>
    <WatchPreviewCard v-if="preview" :preview="preview" />
    <div v-if="error" class="error">✗ {{ error }}</div>
    <template #actions>
      <BaseButton variant="ghost" @click="open = false">Отмена</BaseButton>
      <BaseButton :loading="checking" :disabled="!url" @click="check">Проверить ссылку</BaseButton>
      <BaseButton type="submit" variant="primary" :loading="adding" :disabled="!canAdd">Добавить</BaseButton>
    </template>
  </BaseDialog>
</template>

<style scoped>
.howto { margin: 0; padding-left: 18px; color: var(--text-2); font-size: 13px; }
.error { background: var(--crit-soft); border-radius: 12px; padding: 10px 12px; font-size: 13px; color: var(--crit); font-weight: 600; }
</style>
