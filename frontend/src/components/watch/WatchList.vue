<script setup lang="ts">
import { useAppStore } from '@/stores/app'
import EmptyWatches from './EmptyWatches.vue'
import WatchCard from './WatchCard.vue'

defineEmits<{ add: [] }>()
const app = useAppStore()
</script>

<template>
  <template v-if="app.state">
    <WatchCard v-for="w in app.watches" :key="w.id" :watch="w" />
    <EmptyWatches v-if="!app.watches.length" @add="$emit('add')" />
  </template>
</template>
