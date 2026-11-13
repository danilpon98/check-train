/**
 * Сирена на WebAudio. Браузер разрешает звук только после взаимодействия с
 * страницей, поэтому контекст «разблокируется» первым кликом или нажатием клавиши.
 */
let ctx: AudioContext | null = null

export function unlockAudio(): void {
  try {
    if (!ctx) {
      const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (!AC) return
      ctx = new AC()
    }
    if (ctx.state === 'suspended') void ctx.resume()
  } catch {
    /* WebAudio недоступен */
  }
}

export function audioReady(): boolean {
  return !!ctx && ctx.state === 'running'
}

/** Шесть чередующихся сигналов ~2 с. Возвращает false, если звук сейчас невозможен. */
export function playSiren(): boolean {
  if (!ctx || ctx.state !== 'running') return false
  const t = ctx.currentTime
  for (let i = 0; i < 6; i++) {
    const o = ctx.createOscillator()
    const g = ctx.createGain()
    o.type = 'square'
    o.frequency.value = i % 2 ? 660 : 990
    const start = t + i * 0.35
    g.gain.setValueAtTime(0.0001, start)
    g.gain.exponentialRampToValueAtTime(0.25, start + 0.02)
    g.gain.exponentialRampToValueAtTime(0.0001, start + 0.3)
    o.connect(g).connect(ctx.destination)
    o.start(start)
    o.stop(start + 0.32)
  }
  return true
}

export function installAudioUnlock(): void {
  window.addEventListener('pointerdown', unlockAudio, { passive: true })
  window.addEventListener('keydown', unlockAudio, { passive: true })
}
