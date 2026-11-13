<script setup lang="ts">
import { useAppStore } from '@/stores/app'

const app = useAppStore()
</script>

<template>
  <div v-if="app.online === false" class="lost" role="status">
    Нет связи с сервисом — переподключаюсь…
  </div>
</template>

<style scoped>
.lost { background: var(--warn-soft); color: var(--text); text-align: center; padding: 6px; font-size: 13px; }
</style>
