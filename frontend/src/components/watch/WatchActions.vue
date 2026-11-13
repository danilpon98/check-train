<script setup lang="ts">
import { ref } from 'vue'
import type { Watch } from '@/api/types'
import AppIcon from '@/components/common/AppIcon.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import PromptDialog from '@/components/common/PromptDialog.vue'
import { useAppStore } from '@/stores/app'
import { useEventsStore } from '@/stores/events'

const props = defineProps<{ watch: Watch; checking: boolean }>()
const app = useAppStore()
const events = useEventsStore()
const renameOpen = ref(false)
const deleteOpen = ref(false)

async function remove() {
  await app.remove(props.watch.id)
  await events.load(true)
}
</script>

<template>
  <div class="actions">
    <BaseButton
      size="sm"
      :loading="checking"
      :disabled="!watch.enabled || watch.status === 'finished'"
      @click="app.checkWatch(watch.id)"
    ><template v-if="!checking">⟳</template> Проверить</BaseButton>
    <BaseButton v-if="watch.status !== 'finished'" size="sm" @click="app.setEnabled(watch.id, !watch.enabled)">
      {{ watch.enabled ? '⏸ Пауза' : '▶ Возобновить' }}
    </BaseButton>
    <BaseButton size="sm" :href="watch.url">↗ Сайт</BaseButton>
    <BaseButton size="sm" @click="renameOpen = true"><AppIcon name="pencil" :size="14" /> Переименовать</BaseButton>
    <BaseButton size="sm" variant="danger" @click="deleteOpen = true"><AppIcon name="trash" :size="14" /> Удалить</BaseButton>

    <PromptDialog
      v-model:open="renameOpen"
      title="Переименовать"
      label="Название (пусто — по умолчанию)"
      :initial="watch.name ?? ''"
      placeholder="Например: К маме, 27 ноября"
      @submit="(v) => app.rename(watch.id, v)"
    />
    <ConfirmDialog
      v-model:open="deleteOpen"
      title="Удалить поезд?"
      :message="`«${watch.title}» будет удалён вместе с историей проверок и событиями.`"
      confirm-label="Удалить"
      danger
      @confirm="remove"
    />
  </div>
</template>

<style scoped>
.actions { display: flex; gap: 6px; flex-wrap: wrap; }
</style>
