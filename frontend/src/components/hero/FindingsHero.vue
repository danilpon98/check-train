<script setup lang="ts">
import { computed } from 'vue'
import BaseButton from '@/components/common/BaseButton.vue'
import { type Finding, useAppStore } from '@/stores/app'
import { usePrefsStore } from '@/stores/prefs'

/** Яркий баннер: виден, пока прямо сейчас есть свободная кабинка или новый вагон. */
const app = useAppStore()
const prefs = usePrefsStore()

const key = computed(() => app.findings.map((f) => f.key).sort().join('|'))
const visible = computed(() => app.findings.length > 0 && prefs.heroDismissed !== key.value)

const title = computed(() => {
  const cabin = app.findings.some((f) => f.kind === 'cabin')
  const car = app.findings.some((f) => f.kind === 'car')
  if (cabin && car) return 'Есть свободная кабинка и новый вагон!'
  return cabin ? 'Есть свободная кабинка — 4 места!' : 'Появился новый вагон!'
})

const groups = computed(() => {
  const map = new Map<string, { watchTitle: string; route: string | null; url: string; items: Finding[] }>()
  for (const f of app.findings) {
    if (!map.has(f.watch.id)) map.set(f.watch.id, { watchTitle: f.watch.title, route: f.watch.route, url: f.watch.url, items: [] })
    map.get(f.watch.id)!.items.push(f)
  }
  return [...map.values()]
})
</script>

<template>
  <div v-if="visible" class="hero" role="alert">
    <h2>🚨 {{ title }}</h2>
    <div v-for="g in groups" :key="g.url" class="group">
      <small>{{ g.watchTitle }}<template v-if="g.route"> · {{ g.route }}</template></small>
      <ul>
        <li v-for="f in g.items" :key="f.key">
          {{ f.kind === 'cabin' ? '🟢 Вагон' : '🆕 Новый вагон' }} <b>{{ f.car }}</b> ({{ f.carType }}): <b>{{ f.text }}</b>
        </li>
      </ul>
      <BaseButton class="buy" size="lg" :href="g.url">🎫 Купить на сайте</BaseButton>
    </div>
    <BaseButton class="hide" variant="ghost" size="sm" @click="prefs.heroDismissed = key">Скрыть до следующей находки</BaseButton>
  </div>
</template>

<style scoped>
.hero {
  border-radius: var(--radius); padding: 20px 22px; margin-bottom: 20px; color: #fff;
  background: linear-gradient(135deg, #0a8f0a, #0ca30c 45%, #19b84a);
  box-shadow: 0 8px 30px rgba(12, 163, 12, .35);
  animation: pulse 2.2s ease-in-out infinite;
}
@keyframes pulse { 50% { box-shadow: 0 8px 46px rgba(12, 163, 12, .6); } }
@media (prefers-reduced-motion: reduce) { .hero { animation: none; } }
h2 { font-size: 24px; letter-spacing: .3px; }
.group { margin-top: 12px; }
.group + .group { border-top: 1px solid rgba(255, 255, 255, .3); padding-top: 12px; }
small { opacity: .85; }
ul { margin: 8px 0 14px; padding: 0; list-style: none; font-size: 17px; }
li { padding: 3px 0; }
li b { font-size: 19px; }
.buy { background: #fff; color: #0a7a0a; border-color: #fff; font-weight: 700; }
.buy:hover { background: #f0fff0; }
.hide { color: #fff; margin-top: 10px; }
</style>
