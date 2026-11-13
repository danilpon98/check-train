<script setup lang="ts">
import { ref, watch } from 'vue'
import BaseButton from './BaseButton.vue'
import BaseDialog from './BaseDialog.vue'

const props = withDefaults(defineProps<{ title: string; label: string; initial?: string; placeholder?: string; maxlength?: number }>(), {
  initial: '',
  maxlength: 120,
})
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ submit: [value: string] }>()
const value = ref(props.initial)

watch(open, (v) => { if (v) value.value = props.initial })

function submit() {
  open.value = false
  emit('submit', value.value)
}
</script>

<template>
  <BaseDialog v-model:open="open" :title="title" @submit="submit">
    <label class="field">{{ label }}
      <input v-model="value" :placeholder="placeholder" :maxlength="maxlength" autofocus>
    </label>
    <template #actions>
      <BaseButton variant="ghost" @click="open = false">Отмена</BaseButton>
      <BaseButton type="submit" variant="primary">Сохранить</BaseButton>
    </template>
  </BaseDialog>
</template>
