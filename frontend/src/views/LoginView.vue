<script setup lang="ts">
import { useIntervalFn } from '@vueuse/core'
import { computed, onMounted, ref } from 'vue'
import { ApiError } from '@/api/client'
import PasswordField from '@/components/auth/PasswordField.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import CheckboxField from '@/components/common/CheckboxField.vue'
import { isLockout, useAuthStore } from '@/stores/auth'
import { duration } from '@/utils/format'

/** Страница входа по паролю (WEB_PASSWORD). */
const auth = useAuthStore()

const password = ref('')
const remember = ref(true)
const busy = ref(false)
const error = ref('')
/** тряска карточки при неверном пароле (класс переключается, чтобы анимация шла заново) */
const shaking = ref(false)
/** момент окончания блокировки после 5 неудачных попыток */
const lockedUntil = ref<number | null>(null)
const now = ref(Date.now())
const field = ref<InstanceType<typeof PasswordField> | null>(null)
const icon = `${import.meta.env.BASE_URL}icon-192.png`

useIntervalFn(() => {
  now.value = Date.now()
  if (lockedUntil.value && now.value >= lockedUntil.value) {
    lockedUntil.value = null
    error.value = ''
  }
}, 1000)

const lockLeft = computed(() => (lockedUntil.value ? Math.max(0, (lockedUntil.value - now.value) / 1000) : 0))
const locked = computed(() => lockLeft.value > 0)

const notice = computed(() => {
  if (auth.reason === 'expired') return 'Сессия истекла — войдите снова.'
  if (auth.reason === 'signed-out') return 'Вы вышли из панели.'
  return ''
})

onMounted(() => field.value?.focus())

async function submit() {
  if (!password.value || busy.value || locked.value) return
  busy.value = true
  error.value = ''
  try {
    await auth.login(password.value, remember.value)
  } catch (e) {
    if (isLockout(e)) {
      lockedUntil.value = Date.now() + (e.retryAfter ?? 900) * 1000
      error.value = 'Слишком много неудачных попыток.'
    } else if (e instanceof ApiError && e.status === 401) {
      error.value = e.message
    } else {
      error.value = 'Сервис не отвечает. Проверьте, что он запущен, и попробуйте снова.'
    }
    password.value = ''
    shaking.value = false
    requestAnimationFrame(() => { shaking.value = true })
    field.value?.focus()
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="login">
    <div class="glow" aria-hidden="true" />
    <form class="card" :class="{ shake: shaking }" novalidate @submit.prevent="submit" @animationend="shaking = false">
      <header class="head">
        <img :src="icon" alt="" width="56" height="56" class="logo">
        <h1>trainwatch</h1>
        <p class="sub">Вход в панель отслеживания вагонов</p>
      </header>

      <p v-if="notice && !error" class="notice" role="status">{{ notice }}</p>

      <!-- скрытое имя пользователя: менеджеры паролей запоминают пару «логин — пароль» -->
      <input type="text" name="username" value="trainwatch" autocomplete="username" hidden readonly>
      <PasswordField ref="field" v-model="password" :invalid="!!error" :disabled="locked" />

      <CheckboxField
        v-model="remember"
        class="remember"
        :label="`Запомнить меня на ${auth.rememberDays} дней`"
        :disabled="locked"
      />

      <div v-if="error" class="error" role="alert">
        {{ error }}
        <template v-if="locked"> Повторите через <b class="num">{{ duration(lockLeft) }}</b>.</template>
      </div>

      <BaseButton type="submit" variant="primary" size="lg" class="submit" :loading="busy" :disabled="!password || locked">
        {{ locked ? 'Вход временно заблокирован' : 'Войти' }}
      </BaseButton>
    </form>
  </main>
</template>

<style scoped>
.login {
  position: relative; min-height: 100vh; min-height: 100dvh; display: grid; place-items: center;
  padding: 24px 16px; overflow: hidden; background: var(--bg);
}
/* мягкое свечение акцентного цвета за карточкой */
.glow {
  position: absolute; inset: auto; width: 720px; height: 720px; border-radius: 50%; top: -260px;
  background: radial-gradient(circle, color-mix(in srgb, var(--accent) 22%, transparent), transparent 65%);
  pointer-events: none;
}
.card {
  position: relative; width: 100%; max-width: 380px; display: flex; flex-direction: column; gap: 14px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: 28px 24px 20px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, .04), 0 18px 50px rgba(0, 0, 0, .10);
}
.head { text-align: center; margin-bottom: 4px; }
.logo { border-radius: 14px; box-shadow: 0 6px 18px color-mix(in srgb, var(--accent) 35%, transparent); }
h1 { font-size: 24px; margin-top: 12px; letter-spacing: .2px; }
.sub { margin: 4px 0 0; color: var(--text-2); font-size: 14px; }
.notice {
  margin: 0; padding: 10px 12px; border-radius: 10px; font-size: 13px;
  background: var(--accent-soft); color: var(--accent-ink);
}
.remember { font-size: 14px; }
.error {
  padding: 10px 12px; border-radius: 10px; font-size: 13px; line-height: 1.4;
  background: var(--crit-soft); color: var(--crit); font-weight: 500;
}
.submit { width: 100%; margin-top: 10px; }
.shake { animation: shake .4s ease; }
@keyframes shake {
  20%, 60% { transform: translateX(-6px); }
  40%, 80% { transform: translateX(6px); }
}
@media (prefers-reduced-motion: reduce) { .shake { animation: none; } }
@media (max-width: 420px) {
  .card { padding: 24px 18px 18px; border-radius: 16px; }
}
</style>
