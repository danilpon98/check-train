<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useSettingsStore } from '@/stores/settings'

const { draft } = storeToRefs(useSettingsStore())
</script>

<template>
  <details v-if="draft" class="adv">
    <summary>Дополнительно</summary>
    <div class="row">
      <label class="field">Случайная добавка к интервалу, с
        <input v-model.number="draft.jitter_seconds" type="number" min="0" max="600">
      </label>
      <label class="field">Пауза после ошибки, с
        <input v-model.number="draft.retry_delay_seconds" type="number" min="10" max="3600">
      </label>
    </div>
    <div class="row">
      <label class="field">Предупреждать после N ошибок подряд
        <input v-model.number="draft.failure_alert_threshold" type="number" min="1" max="100">
      </label>
      <label class="field">Подтверждений «пустого» ответа
        <input v-model.number="draft.confirm_empty_checks" type="number" min="1" max="10">
      </label>
    </div>
  </details>
</template>

<style scoped>
summary { cursor: pointer; font-weight: 600; padding: 4px 0; }
.adv .row { margin-top: 8px; }
</style>
