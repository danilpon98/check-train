import { createPinia, setActivePinia } from 'pinia'

/** Свежий Pinia для каждого теста (без @pinia/testing — нам не нужны моки экшенов). */
export function createTestingPinia() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return pinia
}
