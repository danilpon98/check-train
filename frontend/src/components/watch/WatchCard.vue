<script setup lang="ts">
import { computed } from 'vue'
import type { Watch } from '@/api/types'
import BasePanel from '@/components/common/BasePanel.vue'
import { useAppStore } from '@/stores/app'
import CarGrid from './CarGrid.vue'
import WatchActions from './WatchActions.vue'
import WatchHeader from './WatchHeader.vue'
import WatchHistory from './WatchHistory.vue'
import WatchKpis from './WatchKpis.vue'
import WatchTiming from './WatchTiming.vue'

const props = defineProps<{ watch: Watch }>()
const app = useAppStore()
const checking = computed(() => app.checking.has(props.watch.id) || props.watch.status === 'checking')
</script>

<template>
  <BasePanel as="article" class="watch">
    <div class="top">
      <WatchHeader :watch="watch" :checking="checking" />
      <WatchActions :watch="watch" :checking="checking" />
    </div>
    <WatchTiming :watch="watch" />
    <WatchKpis :totals="watch.totals" />
    <CarGrid :watch="watch" />
    <WatchHistory :watch="watch" />
  </BasePanel>
</template>

<style scoped>
.watch { margin-bottom: 20px; }
.top { display: flex; gap: 14px; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; }
</style>
