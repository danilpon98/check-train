<template>
  <div class="legend">
    <span><i style="background: var(--seat-free)" />свободно</span>
    <span><i style="background: var(--seat-taken)" />занято</span>
    <span><i style="background: var(--good)" />кабинка свободна целиком</span>
    <span>верхний ряд — верхние полки, снизу — боковые</span>
  </div>
</template>

<style scoped>
.legend { display: flex; gap: 14px; color: var(--muted); font-size: 12px; flex-wrap: wrap; margin-top: 6px; }
i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; vertical-align: -1px; margin-right: 5px; }
</style>
