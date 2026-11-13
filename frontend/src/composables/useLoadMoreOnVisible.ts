import { useIntersectionObserver } from '@vueuse/core'
import { type MaybeRefOrGetter, nextTick, type Ref, ref, toValue, watch } from 'vue'

interface Options {
  /** включено ли (на мобильном — нет, там кнопка) */
  enabled: MaybeRefOrGetter<boolean>
  /** можно ли грузить прямо сейчас: есть ещё страницы, не идёт загрузка, нет ошибки */
  canLoad: MaybeRefOrGetter<boolean>
  load: () => unknown
  /** начинать подгрузку заранее, за столько пикселей до конца списка */
  marginPx?: number
}

/**
 * Бесконечная прокрутка: когда маркер в конце списка приближается к видимой области
 * контейнера `root`, вызывается `load`.
 *
 * Две тонкости:
 *  1. IntersectionObserver сообщает только об ИЗМЕНЕНИИ видимости. Если после подгрузки список
 *     всё ещё короче контейнера, маркер остаётся видимым и нового события не будет —
 *     поэтому после каждой загрузки проверяем снова.
 *  2. Но и верить старому «виден» сразу после загрузки нельзя: новые элементы уже отодвинули
 *     маркер, а IntersectionObserver сообщит об этом лишь на следующем кадре — иначе одна
 *     прокрутка подгружает несколько страниц подряд. Поэтому положение маркера после
 *     обновления DOM измеряется синхронно.
 */
export function useLoadMoreOnVisible(sentinel: Ref<HTMLElement | null>, root: Ref<HTMLElement | null>, opts: Options) {
  const margin = opts.marginPx ?? 200
  const visible = ref(false)

  useIntersectionObserver(
    sentinel,
    ([entry]) => { visible.value = !!entry?.isIntersecting },
    { root, rootMargin: `${margin}px 0px` },
  )

  /** маркер в пределах контейнера (с запасом margin) — по фактической геометрии, без ожидания кадра */
  function isNear(): boolean {
    const s = sentinel.value
    if (!s) return false
    const box = root.value?.getBoundingClientRect() ?? { top: 0, bottom: window.innerHeight }
    const r = s.getBoundingClientRect()
    return r.top <= box.bottom + margin && r.bottom >= box.top - margin
  }

  watch(
    () => [visible.value, toValue(opts.enabled), toValue(opts.canLoad)] as const,
    async ([isVisible, enabled, canLoad]) => {
      if (!isVisible || !enabled || !canLoad) return
      await nextTick()                       // DOM уже содержит только что загруженную страницу
      if (toValue(opts.enabled) && toValue(opts.canLoad) && isNear()) void opts.load()
    },
  )

  return { visible }
}
