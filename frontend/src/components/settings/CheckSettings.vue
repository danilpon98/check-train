<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useSettingsStore } from '@/stores/settings'
import SettingsSection from './SettingsSection.vue'

const { draft } = storeToRefs(useSettingsStore())
const PRESETS = [5, 10, 15, 30, 60]
</script>

<template>
  <SettingsSection v-if="draft" title="Проверка">
    <div class="row">
      <label class="field">Интервал, минут
        <input v-model.number="draft.check_interval_minutes" type="number" min="1" max="1440" step="1" required>
      </label>
      <div class="presets" role="group" aria-label="Быстрый выбор интервала">
        <button
          v-for="p in PRESETS"
          :key="p"
          type="button"
          :class="{ on: draft.check_interval_minutes === p }"
          @click="draft.check_interval_minutes = p"
        >{{ p }}</button>
      </div>
    </div>
    <p class="hint" :class="{ warn: draft.check_interval_minutes < 5 }">
      Сайт стоит за защитой от ботов: чаще раза в 5 минут — риск блокировки IP.
    </p>
  </SettingsSection>
</template>

<style scoped>
.presets { display: flex; gap: 4px; }
.presets button { border: 1px solid var(--border); background: var(--surface); border-radius: 8px; padding: 6px 10px; cursor: pointer; }
.presets button.on { background: var(--accent); color: #fff; border-color: var(--accent); }
</style>
