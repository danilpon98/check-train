<script setup lang="ts">
import { computed } from 'vue'
import type { Watch } from '@/api/types'
import { useNow } from '@/composables/useNow'
import { duration, fmtKZ } from '@/utils/format'
import WatchStatusPill from './WatchStatusPill.vue'

const props = defineProps<{ watch: Watch; checking: boolean }>()
const now = useNow()

const departure = computed(() => {
  const w = props.watch
  if (!w.departure) return null
  const left = (new Date(w.departure).getTime() - now.value) / 1000
  return {
    text: w.departure_text ?? fmtKZ(w.departure),
    countdown: left > 0 ? `через ${duration(left)}` : 'отправился',
  }
})
</script>

<template>
  <div class="head">
    <div>
      <span class="badge">{{ watch.train }}</span>
      <span class="title">{{ watch.route || watch.title }}</span>
    </div>
    <div class="sub">
      <span v-if="watch.name">{{ watch.name }}</span>
      <span v-if="departure">🕒 {{ departure.text }} <span class="muted">· {{ departure.countdown }}</span></span>
      <span v-if="watch.carrier">{{ watch.carrier }}</span>
      <WatchStatusPill :status="checking ? 'checking' : watch.status" />
    </div>
  </div>
</template>

<style scoped>
.badge {
  display: inline-block; background: var(--accent); color: #fff; font-weight: 700; padding: 4px 10px;
  border-radius: 8px; font-size: 18px; letter-spacing: .5px; margin-right: 10px; vertical-align: middle;
}
.title { font-size: 20px; font-weight: 700; vertical-align: middle; }
.sub { color: var(--text-2); margin-top: 6px; display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }
</style>
