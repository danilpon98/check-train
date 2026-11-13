<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AlarmOverlay from '@/components/alarm/AlarmOverlay.vue'
import ToastHost from '@/components/common/ToastHost.vue'
import AddWatchDialog from '@/components/dialogs/AddWatchDialog.vue'
import SettingsDialog from '@/components/dialogs/SettingsDialog.vue'
import EventFeed from '@/components/feed/EventFeed.vue'
import FindingsHero from '@/components/hero/FindingsHero.vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import ConnectionBanner from '@/components/layout/ConnectionBanner.vue'
import SetupChecklist from '@/components/setup/SetupChecklist.vue'
import WatchList from '@/components/watch/WatchList.vue'
import { useLiveStream } from '@/composables/useLiveStream'
import { useServiceWorkerMessages } from '@/composables/useServiceWorkerMessages'
import { installAudioUnlock } from '@/composables/useSiren'
import { TEST_ALARM, useAlarmStore } from '@/stores/alarm'
import { useAppStore } from '@/stores/app'
import { useEventsStore } from '@/stores/events'
import { usePushStore } from '@/stores/push'

const app = useAppStore()
const events = useEventsStore()
const push = usePushStore()
const alarm = useAlarmStore()

const addOpen = ref(false)
const settingsOpen = ref(false)

useLiveStream()
useServiceWorkerMessages()

onMounted(async () => {
  installAudioUnlock()
  if (location.hash === '#test-alarm') alarm.show(TEST_ALARM)
  // данные не ждут Service Worker — его регистрация бывает долгой
  void events.load(true)
  await app.refresh()
  await push.init()
  await push.sync()
})
</script>

<template>
  <AppHeader @add="addOpen = true" @open-settings="settingsOpen = true" />
  <ConnectionBanner />

  <main class="layout">
    <section class="main">
      <FindingsHero />
      <SetupChecklist @add="addOpen = true" @open-settings="settingsOpen = true" />
      <WatchList @add="addOpen = true" />
    </section>
    <aside class="side">
      <EventFeed />
    </aside>
  </main>

  <AddWatchDialog v-model:open="addOpen" />
  <SettingsDialog v-model:open="settingsOpen" />
  <AlarmOverlay />
  <ToastHost />
</template>

<style scoped>
.layout {
  display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 20px;
  max-width: 1440px; margin: 0 auto; padding: 20px;
}
.main, .side { min-width: 0; }
.side > :deep(.feed-panel) { position: sticky; top: 76px; max-height: calc(100vh - 96px); }
@media (max-width: 1100px) {
  .layout { grid-template-columns: minmax(0, 1fr); }
  .side > :deep(.feed-panel) { position: static; max-height: none; }
}
@media (max-width: 640px) {
  .layout { padding: 12px 16px; }
}
</style>
