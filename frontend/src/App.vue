<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import DashboardView from '@/views/DashboardView.vue'
import LoginView from '@/views/LoginView.vue'

/**
 * Ворота: пока статус входа не известен — пустая заставка (без мигания страницы входа),
 * дальше — вход или панель. Панель монтируется только после входа: до этого ни данных,
 * ни потока обновлений не запрашиваем.
 */
const auth = useAuthStore()
const needLogin = computed(() => auth.required && !auth.authenticated)

onMounted(() => auth.check())
</script>

<template>
  <div v-if="!auth.checked" class="splash" aria-busy="true" />
  <LoginView v-else-if="needLogin" />
  <DashboardView v-else />
</template>

<style scoped>
.splash { min-height: 100vh; background: var(--bg); }
</style>
