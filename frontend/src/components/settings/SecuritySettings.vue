<script setup lang="ts">
import { ref } from 'vue'
import BaseButton from '@/components/common/BaseButton.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { useAuthStore } from '@/stores/auth'
import SettingsSection from './SettingsSection.vue'

/** Вход и сессии. Показывается, только если задан WEB_PASSWORD. */
const auth = useAuthStore()
const confirmAll = ref(false)
const busy = ref(false)

async function logout(everywhere: boolean) {
  busy.value = true
  await auth.logout(everywhere)
}
</script>

<template>
  <SettingsSection v-if="auth.required" title="Вход и безопасность">
    <p class="hint">
      Сессия с галочкой «Запомнить» действует {{ auth.rememberDays }} дней с последнего визита, без неё — до закрытия
      браузера (не дольше 12 часов). Смена <code>WEB_PASSWORD</code> на сервере завершает все сессии.
      Push и Telegram от входа не зависят.
    </p>
    <div class="row">
      <BaseButton :loading="busy" @click="logout(false)">Выйти</BaseButton>
      <BaseButton variant="danger" :disabled="busy" @click="confirmAll = true">Выйти на всех устройствах</BaseButton>
    </div>
    <ConfirmDialog
      v-model:open="confirmAll"
      title="Выйти на всех устройствах?"
      message="Все браузеры и телефоны, где выполнен вход, потребуют пароль снова. Уведомления продолжат приходить."
      confirm-label="Выйти везде"
      danger
      @confirm="logout(true)"
    />
  </SettingsSection>
</template>

<style scoped>
code { font-size: 11px; background: var(--surface-2); padding: 1px 5px; border-radius: 4px; }
</style>
