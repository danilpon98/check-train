<script setup lang="ts">
import { useMediaQuery } from '@vueuse/core'
import { computed, ref } from 'vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BasePanel from '@/components/common/BasePanel.vue'
import SegmentedControl from '@/components/common/SegmentedControl.vue'
import { useLoadMoreOnVisible } from '@/composables/useLoadMoreOnVisible'
import { FEED_FILTERS, useEventsStore } from '@/stores/events'
import { DESKTOP_QUERY } from '@/utils/breakpoints'
import EventItem from './EventItem.vue'

/**
 * Лента событий.
 *  - Десктоп: лента в боковой колонке со своей прокруткой → бесконечная подгрузка при прокрутке.
 *  - Мобильный: лента прокручивается вместе со страницей → следующая страница по кнопке.
 */
const events = useEventsStore()
const isDesktop = useMediaQuery(DESKTOP_QUERY)

const list = ref<HTMLElement | null>(null)
const sentinel = ref<HTMLElement | null>(null)

const filter = computed({
  get: () => events.filter,
  set: (v: string) => {
    list.value?.scrollTo({ top: 0 })
    void events.setFilter(v)
  },
})

const canLoad = computed(() => events.hasMore && !events.loading && !events.error)
useLoadMoreOnVisible(sentinel, list, { enabled: isDesktop, canLoad, load: events.loadMore })

const empty = computed(() => !events.items.length && !events.loading && !events.error)
</script>

<template>
  <BasePanel class="feed-panel">
    <div class="head">
      <h2>События</h2>
      <SegmentedControl v-model="filter" :options="FEED_FILTERS" label="Фильтр событий" />
    </div>

    <ol ref="list" class="feed" :class="{ scrollable: isDesktop }" :aria-busy="events.loading">
      <EventItem
        v-for="e in events.items"
        :key="e.id ?? e.at"
        :event="e"
        :highlight="e.id !== null && e.id === events.highlightId"
      />
      <li v-if="empty" class="note">Событий пока нет</li>

      <!-- десктоп: маркер конца списка для бесконечной подгрузки -->
      <li v-if="isDesktop" ref="sentinel" class="sentinel" aria-hidden="true" />
      <li v-if="isDesktop && events.loading && events.items.length" class="note">Загрузка…</li>
      <li v-if="isDesktop && !events.hasMore && events.items.length > 0 && !events.loading" class="note end">
        Это все события
      </li>
    </ol>

    <div v-if="events.error" class="error" role="alert">
      Не удалось загрузить события: {{ events.error }}
      <BaseButton size="sm" @click="events.items.length ? events.loadMore() : events.load(true)">Повторить</BaseButton>
    </div>

    <!-- мобильный: следующая страница по кнопке -->
    <BaseButton
      v-if="!isDesktop && events.hasMore && !events.error"
      class="more"
      :loading="events.loading"
      @click="events.loadMore()"
    >Показать ещё</BaseButton>
  </BasePanel>
</template>

<style scoped>
.feed-panel { display: flex; flex-direction: column; }
.head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.feed { list-style: none; margin: 0; padding: 0; min-height: 120px; }
/* десктоп: своя прокрутка внутри боковой колонки (высоту ограничивает App.vue) */
.feed.scrollable { overflow-y: auto; flex: 1; overscroll-behavior: contain; }
.sentinel { height: 1px; list-style: none; }
.note { color: var(--muted); padding: 14px 4px; text-align: center; font-size: 13px; }
.note.end { font-size: 12px; }
.error {
  display: flex; gap: 8px; align-items: center; justify-content: space-between; flex-wrap: wrap;
  margin-top: 8px; padding: 8px 12px; border-radius: 10px; background: var(--crit-soft); font-size: 13px;
}
.more { margin-top: 8px; width: 100%; }
</style>
