<script setup lang="ts">
import BaseButton from '@/components/common/BaseButton.vue'
import BasePanel from '@/components/common/BasePanel.vue'

defineEmits<{ add: [] }>()
</script>

<template>
  <BasePanel class="empty">
    <div class="big" aria-hidden="true">🚆</div>
    <h2>Пока ничего не отслеживается</h2>
    <p>
      Добавьте ссылку на страницу выбора вагона с bilet.railways.kz — сервис будет проверять её
      и сообщит, когда появится новый вагон или освободится целая кабинка.
    </p>
    <BaseButton variant="primary" @click="$emit('add')">＋ Добавить поезд</BaseButton>
  </BasePanel>
</template>

<style scoped>
.empty { text-align: center; padding: 40px 20px; }
.big { font-size: 48px; }
p { color: var(--text-2); max-width: 460px; margin: 10px auto 18px; }
</style>
