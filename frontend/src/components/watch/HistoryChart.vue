<script setup lang="ts">
import { useElementSize } from '@vueuse/core'
import { computed, ref } from 'vue'
import type { HistoryRow } from '@/api/types'
import { useNow } from '@/composables/useNow'
import {
  type ChartBox, type Point, areaPath, makeScales, nearestPoint, splitHistory, stepPath, xTicks, yTicks,
} from '@/utils/chart'
import { carsIn, fmtDateTime, seats } from '@/utils/format'

/**
 * Свободные места во времени: одна ступенчатая линия (легенда не нужна — подписана заголовком),
 * зелёные точки — моменты со свободной кабинкой, красные засечки — неудачные проверки.
 * Наведение показывает перекрестие и подсказку с точными значениями.
 */
const props = defineProps<{ rows: HistoryRow[]; hours: number }>()

const wrap = ref<HTMLElement | null>(null)
const { width: measured } = useElementSize(wrap)
const now = useNow()
const H = 180

const data = computed(() => splitHistory(props.rows))
const box = computed<ChartBox>(() => ({
  width: Math.max(280, Math.round(measured.value) || 600),
  height: H,
  margin: { l: 34, r: 12, t: 10, b: 22 },
}))

// «сейчас» с точностью до минуты: computed меняет значение раз в минуту, и только тогда
// пересчитывается график (а не каждую секунду вместе с общими часами)
const nowMinute = computed(() => Math.floor(now.value / 60000) * 60000)

const chart = computed(() => {
  const { points, failures } = data.value
  if (points.length < 2) return null
  const b = box.value
  const nowMin = nowMinute.value
  const s = makeScales(points, b, props.hours, nowMin)
  const line = stepPath(points, s, nowMin)
  const xt = xTicks(s, b.width, b.margin.l)
  return {
    s, line, area: areaPath(line, points, s),
    yTicks: yTicks(s.vmax).map((v) => ({ v, y: s.y(v) })),
    xTicks: xt.map((t, i) => ({ ...t, x: s.x(t.t), anchor: i === 0 ? 'start' : i === xt.length - 1 ? 'end' : 'middle' })),
    cabinDots: points.filter((p) => p.cabins > 0).map((p) => ({ x: s.x(p.t), y: s.y(p.v), key: p.t })),
    fails: failures.filter((f) => f.t >= s.tmin).map((f) => ({ x: s.x(f.t), key: f.t })),
    baseline: s.y(0),
    last: points[points.length - 1].v,
  }
})

const hover = ref<Point | null>(null)
function onMove(e: PointerEvent) {
  const c = chart.value
  const el = e.currentTarget as SVGElement
  if (!c) return
  const r = el.ownerSVGElement!.getBoundingClientRect()
  hover.value = nearestPoint(data.value.points, c.s, ((e.clientX - r.left) * box.value.width) / r.width)
}
const tip = computed(() => {
  const c = chart.value
  const p = hover.value
  if (!c || !p) return null
  const x = c.s.x(p.t)
  const y = c.s.y(p.v)
  return { x, y, left: `${(x / box.value.width) * 100}%`, top: `${y}px`, p }
})
</script>

<template>
  <div ref="wrap" class="wrap">
    <div v-if="!chart" class="empty">
      {{ data.points.length ? 'Нужно хотя бы две проверки, чтобы построить график.' : 'Данных за этот период нет.' }}
    </div>
    <template v-else>
      <svg
        class="chart"
        :viewBox="`0 0 ${box.width} ${box.height}`"
        :height="box.height"
        role="img"
        :aria-label="`График свободных мест: сейчас ${chart.last}`"
      >
        <g class="grid">
          <line v-for="t in chart.yTicks" :key="t.v" :x1="box.margin.l" :x2="box.width - box.margin.r" :y1="t.y" :y2="t.y" />
        </g>
        <g class="axis">
          <text v-for="t in chart.yTicks" :key="`y${t.v}`" :x="box.margin.l - 6" :y="t.y + 4" text-anchor="end">{{ Math.round(t.v) }}</text>
          <text v-for="t in chart.xTicks" :key="`x${t.t}`" :x="t.x" :y="box.height - 4" :text-anchor="t.anchor">{{ t.label }}</text>
        </g>
        <path class="area" :d="chart.area" />
        <path class="line" :d="chart.line" />
        <line v-for="f in chart.fails" :key="`f${f.key}`" class="fail" :x1="f.x" :x2="f.x" :y1="chart.baseline - 6" :y2="chart.baseline" />
        <circle v-for="d in chart.cabinDots" :key="`c${d.key}`" class="cabin-dot" :cx="d.x" :cy="d.y" r="4.5" />
        <template v-if="tip">
          <line class="cross" :x1="tip.x" :x2="tip.x" :y1="box.margin.t" :y2="chart.baseline" />
          <circle class="hover-dot" :cx="tip.x" :cy="tip.y" r="4.5" />
        </template>
        <rect
          class="hit"
          :x="box.margin.l"
          y="0"
          :width="box.width - box.margin.l - box.margin.r"
          :height="box.height"
          @pointermove="onMove"
          @pointerleave="hover = null"
        />
      </svg>
      <div v-if="tip" class="tooltip" :style="{ left: tip.left, top: tip.top }">
        {{ fmtDateTime(tip.p.t) }}<br>
        <b>{{ seats(tip.p.v) }}</b> в {{ carsIn(tip.p.cars) }}
        <template v-if="tip.p.cabins"><br>свободных кабинок: {{ tip.p.cabins }}</template>
      </div>
      <div class="legend">
        <span v-if="chart.cabinDots.length"><i class="dot" />в этот момент была свободная кабинка</span>
        <span v-if="chart.fails.length"><i class="tick" />проверка не удалась</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.wrap { position: relative; min-width: 0; }
.chart { width: 100%; display: block; overflow: visible; }
.grid line { stroke: var(--grid); }
.axis text { fill: var(--muted); font-size: 11px; }
.line { fill: none; stroke: var(--accent); stroke-width: 2; stroke-linejoin: round; }
.area { fill: var(--accent); opacity: .08; }
.cabin-dot { fill: var(--good); stroke: var(--surface); stroke-width: 2; }
.fail { stroke: var(--crit); stroke-width: 2; }
.cross { stroke: var(--muted); stroke-dasharray: 3 3; }
.hover-dot { fill: var(--accent); stroke: var(--surface); stroke-width: 2; }
.hit { fill: transparent; }
.tooltip {
  position: absolute; pointer-events: none; background: var(--text); color: var(--bg); padding: 6px 9px;
  border-radius: 8px; font-size: 12px; white-space: nowrap; transform: translate(-50%, -110%); z-index: 2;
}
.empty { color: var(--muted); font-size: 13px; padding: 20px 0; text-align: center; }
.legend { display: flex; gap: 14px; color: var(--muted); font-size: 12px; flex-wrap: wrap; margin-top: 6px; }
.legend i { display: inline-block; vertical-align: -1px; margin-right: 5px; }
.dot { width: 10px; height: 10px; border-radius: 50%; background: var(--good); }
.tick { width: 2px; height: 10px; background: var(--crit); }
</style>
