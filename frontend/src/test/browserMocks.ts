/** Заглушки браузерных API, которых нет в jsdom: matchMedia и IntersectionObserver. */

export const media = { desktop: true }
let observers: { cb: IntersectionObserverCallback; el: Element | null }[] = []

export function installBrowserMocks() {
  window.matchMedia = ((query: string) => ({
    matches: media.desktop, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
  observers = []
  globalThis.IntersectionObserver = class {
    private rec: { cb: IntersectionObserverCallback; el: Element | null }
    constructor(cb: IntersectionObserverCallback) { this.rec = { cb, el: null }; observers.push(this.rec) }
    observe(el: Element) { this.rec.el = el }
    unobserve() {}
    disconnect() { this.rec.el = null }
    takeRecords() { return [] }
    root = null; rootMargin = ''; thresholds = []
  } as unknown as typeof IntersectionObserver
}

/** «Прокрутили до конца»: все наблюдаемые маркеры стали (не)видимыми. */
export function setIntersecting(visible = true) {
  for (const o of observers) {
    if (o.el) o.cb([{ isIntersecting: visible, target: o.el } as IntersectionObserverEntry], {} as IntersectionObserver)
  }
}
