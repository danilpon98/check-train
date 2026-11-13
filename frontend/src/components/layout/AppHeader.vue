<script setup lang="ts">
import { computed } from 'vue'
import BaseButton from '@/components/common/BaseButton.vue'
import { useAppStore } from '@/stores/app'
import ChannelChips from './ChannelChips.vue'

const emit = defineEmits<{ add: []; openSettings: [] }>()
const app = useAppStore()
const checkingAll = computed(() => app.checking.size > 0)
const icon = `${import.meta.env.BASE_URL}icon-192.png`
</script>

<template>
  <header class="topbar">
    <div class="brand">
      <img :src="icon" alt="" width="32" height="32">
      <div>
        <div class="name">trainwatch</div>
        <div class="sub">новые вагоны и свободные кабинки</div>
      </div>
    </div>
    <ChannelChips class="status" @open-settings="emit('openSettings')" />
    <div class="actions">
      <BaseButton :loading="checkingAll" title="Проверить все поезда сейчас" @click="app.checkAll()">
        <template v-if="!checkingAll">⟳</template> <span class="hide-sm">Проверить всё</span>
      </BaseButton>
      <BaseButton variant="primary" @click="emit('add')">＋ <span class="hide-sm">Поезд</span></BaseButton>
      <BaseButton icon aria-label="Настройки" title="Настройки" @click="emit('openSettings')">⚙</BaseButton>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  position: sticky; top: 0; z-index: 10;
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  padding: 10px 20px; background: color-mix(in srgb, var(--surface) 92%, transparent);
  backdrop-filter: blur(8px); border-bottom: 1px solid var(--border);
}
.brand { display: flex; gap: 10px; align-items: center; }
.brand img { border-radius: 8px; }
.name { font-weight: 700; font-size: 16px; }
.sub { color: var(--muted); font-size: 12px; }
.status { flex: 1; min-width: 0; }
.actions { display: flex; gap: 8px; }
@media (max-width: 640px) {
  .topbar { padding: 8px 16px; gap: 8px; }
  .sub, .hide-sm { display: none; }
  .status { order: 3; flex-basis: 100%; }
  .actions { margin-left: auto; }
}
</style>
