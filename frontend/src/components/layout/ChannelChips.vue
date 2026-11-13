<script setup lang="ts">
import { useElementSize, useScroll } from '@vueuse/core'
import { computed, ref, watch } from 'vue'
import StatusChip from '@/components/common/StatusChip.vue'
import { useAppStore } from '@/stores/app'
import { usePushStore } from '@/stores/push'

/**
 * Состояние каналов: связь с сервисом, интервал, Push и Telegram.
 * На мобильном — одна строка с горизонтальной прокруткой пальцем; затухание по краю
 * показывает, что за краем есть ещё чипы (только с той стороны, куда можно листать).
 */
const emit = defineEmits<{ openSettings: [] }>()
const app = useAppStore()
const push = usePushStore()

const PUSH_TEXT = {
  on: 'Push: вкл', off: 'Push: выкл', denied: 'Push: запрещён',
  insecure: 'Push: нужен localhost', unsupported: 'Push: не поддерживается',
} as const

const telegram = computed(() => {
  const tg = app.telegram
  if (!tg) return { tone: 'neutral' as const, text: 'Telegram', title: '' }
  let tone: 'ok' | 'warn' | 'bad' | 'neutral' = 'warn'
  let text = 'Telegram: не настроен'
  if (!tg.enabled) { tone = 'neutral'; text = 'Telegram: выкл' }
  else if (tg.configured && tg.last_error) { tone = 'bad'; text = 'Telegram: ошибка' }
  else if (tg.configured) { tone = 'ok'; text = tg.bot_username ? `Telegram: @${tg.bot_username}` : 'Telegram' }
  if (tg.configured && tg.queue > 0) text += ` · в очереди ${tg.queue}`
  return { tone, text, title: tg.last_error ?? '' }
})

const el = ref<HTMLElement | null>(null)
const { arrivedState, measure: measureScroll } = useScroll(el)
const { width } = useElementSize(el)

// Есть ли что листать. Измеряем ПОСЛЕ обновления DOM (flush: 'post'): в момент, когда
// меняются данные, новые чипы ещё не отрисованы и scrollWidth был бы устаревшим.
// useScroll пересчитывает «упёрлись в край» только по событию прокрутки — когда чипы
// стали длиннее без прокрутки, пересчитываем вручную.
const overflow = ref(false)
function measure() {
  const e = el.value
  overflow.value = !!e && e.scrollWidth > e.clientWidth + 1
  measureScroll()
}
watch(
  () => [el.value, width.value, telegram.value.text, push.state, app.online, app.state?.server.interval_minutes],
  measure,
  { flush: 'post', immediate: true },
)
const fadeLeft = computed(() => overflow.value && !arrivedState.left)
const fadeRight = computed(() => overflow.value && !arrivedState.right)
</script>

<template>
  <div
    ref="el"
    class="chips"
    :class="{ 'fade-left': fadeLeft, 'fade-right': fadeRight }"
    role="group"
    aria-label="Состояние сервиса и уведомлений"
  >
    <StatusChip v-if="app.online === null">подключение…</StatusChip>
    <StatusChip v-else :tone="app.online ? 'ok' : 'bad'">{{ app.online ? 'онлайн' : 'нет связи' }}</StatusChip>
    <StatusChip v-if="app.state" tone="accent">раз в {{ app.state.server.interval_minutes }} мин</StatusChip>
    <StatusChip clickable :tone="push.state === 'on' ? 'ok' : 'warn'" @click="emit('openSettings')">
      {{ PUSH_TEXT[push.state] }}
    </StatusChip>
    <StatusChip clickable :tone="telegram.tone" :title="telegram.title" @click="emit('openSettings')">
      {{ telegram.text }}
    </StatusChip>
  </div>
</template>

<style scoped>
.chips { display: flex; gap: 6px; flex-wrap: wrap; }

@media (max-width: 640px) {
  /* одна строка, листается пальцем; полоса прокрутки скрыта — на телефоне её и так нет */
  .chips {
    flex-wrap: nowrap;
    overflow-x: auto;
    overscroll-behavior-x: contain;
    scroll-snap-type: x proximity;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
    /* растягиваем до краёв экрана, чтобы чипы уезжали под край, а не обрезались у отступа */
    margin: 0 -16px;
    padding: 2px 16px;
    scroll-padding-inline: 16px;
  }
  .chips::-webkit-scrollbar { display: none; }
  .chips > :deep(*) { flex: none; scroll-snap-align: start; }
  .fade-right { mask-image: linear-gradient(to right, #000 calc(100% - 40px), transparent); }
  .fade-left { mask-image: linear-gradient(to left, #000 calc(100% - 40px), transparent); }
  .fade-left.fade-right {
    mask-image: linear-gradient(to right, transparent, #000 40px, #000 calc(100% - 40px), transparent);
  }
}
</style>
