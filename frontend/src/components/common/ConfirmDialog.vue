<script setup lang="ts">
import BaseButton from './BaseButton.vue'
import BaseDialog from './BaseDialog.vue'

withDefaults(defineProps<{ title: string; message: string; confirmLabel?: string; danger?: boolean }>(), {
  confirmLabel: 'Подтвердить',
})
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ confirm: [] }>()

function confirm() {
  open.value = false
  emit('confirm')
}
</script>

<template>
  <BaseDialog v-model:open="open" :title="title" @submit="confirm">
    <p class="msg">{{ message }}</p>
    <template #actions>
      <BaseButton variant="ghost" @click="open = false">Отмена</BaseButton>
      <BaseButton type="submit" :variant="danger ? 'danger' : 'primary'">{{ confirmLabel }}</BaseButton>
    </template>
  </BaseDialog>
</template>

<style scoped>
.msg { margin: 0; color: var(--text-2); }
</style>
