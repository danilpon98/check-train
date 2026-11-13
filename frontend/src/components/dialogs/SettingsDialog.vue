<script setup lang="ts">
import { watch } from 'vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseDialog from '@/components/common/BaseDialog.vue'
import AdvancedSettings from '@/components/settings/AdvancedSettings.vue'
import CheckSettings from '@/components/settings/CheckSettings.vue'
import PushSettings from '@/components/settings/PushSettings.vue'
import SecuritySettings from '@/components/settings/SecuritySettings.vue'
import TelegramSettings from '@/components/settings/TelegramSettings.vue'
import { useSettingsStore } from '@/stores/settings'
import { useToastStore } from '@/stores/toast'

const open = defineModel<boolean>('open', { required: true })
const settings = useSettingsStore()
const toast = useToastStore()

watch(open, async (v) => {
  if (!v) return
  try {
    await settings.load()
  } catch (e) {
    toast.error(e)
    open.value = false
  }
})

async function save() {
  if (await settings.save()) toast.show('Настройки сохранены')
}
</script>

<template>
  <BaseDialog v-model:open="open" title="Настройки" wide @submit="save">
    <template v-if="settings.draft">
      <CheckSettings />
      <PushSettings @close="open = false" />
      <TelegramSettings />
      <SecuritySettings />
      <AdvancedSettings />
    </template>
    <p v-else class="hint">Загрузка…</p>
    <div class="error" role="alert">{{ settings.error }}</div>
    <template #actions>
      <BaseButton variant="ghost" @click="open = false">Закрыть</BaseButton>
      <BaseButton type="submit" variant="primary" :loading="settings.saving">Сохранить</BaseButton>
    </template>
  </BaseDialog>
</template>

<style scoped>
.error { color: var(--crit); font-size: 13px; min-height: 1em; }
</style>
