<script setup lang="ts">
import { ref } from 'vue'

/** Поле пароля: показать/скрыть, предупреждение о Caps Lock. */
defineProps<{ invalid?: boolean; disabled?: boolean }>()
const model = defineModel<string>({ required: true })
const visible = ref(false)
const capsLock = ref(false)
const input = ref<HTMLInputElement | null>(null)

function onKey(e: KeyboardEvent) {
  capsLock.value = e.getModifierState?.('CapsLock') ?? false
}

defineExpose({ focus: () => input.value?.focus() })
</script>

<template>
  <div class="pw">
    <label for="tw-password" class="label">Пароль</label>
    <div class="box" :class="{ invalid, disabled }">
      <input
        id="tw-password"
        ref="input"
        v-model="model"
        :type="visible ? 'text' : 'password'"
        name="password"
        autocomplete="current-password"
        autocapitalize="off"
        spellcheck="false"
        required
        :disabled="disabled"
        :aria-invalid="invalid"
        aria-describedby="tw-password-hint"
        @keydown="onKey"
        @keyup="onKey"
      >
      <button
        type="button"
        class="eye"
        :aria-label="visible ? 'Скрыть пароль' : 'Показать пароль'"
        :aria-pressed="visible"
        :title="visible ? 'Скрыть пароль' : 'Показать пароль'"
        :disabled="disabled"
        @click="visible = !visible; input?.focus()"
      >
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
          <circle cx="12" cy="12" r="3" />
          <path v-if="visible" d="M3 3l18 18" />
        </svg>
      </button>
    </div>
    <p id="tw-password-hint" class="caps" :class="{ on: capsLock }" aria-live="polite">
      {{ capsLock ? '⇪ Включён Caps Lock' : '' }}
    </p>
  </div>
</template>

<style scoped>
.label { display: block; font-size: 13px; font-weight: 600; color: var(--text-2); margin-bottom: 6px; }
.box {
  display: flex; align-items: center; border: 1.5px solid var(--border); background: var(--bg);
  border-radius: 12px; transition: border-color .15s, box-shadow .15s;
}
.box:focus-within { border-color: var(--accent); box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 18%, transparent); }
.box.invalid { border-color: var(--crit); }
.box.invalid:focus-within { box-shadow: 0 0 0 4px color-mix(in srgb, var(--crit) 18%, transparent); }
.box.disabled { opacity: .6; }
input {
  flex: 1; min-width: 0; border: 0; background: transparent; outline: none;
  padding: 12px 14px; font-size: 16px; /* 16px — iOS не зумит поле при фокусе */
  color: var(--text); letter-spacing: .02em;
}
.eye {
  display: grid; place-items: center; width: 44px; height: 44px; border: 0; background: transparent;
  color: var(--muted); cursor: pointer; border-radius: 10px; margin-right: 2px;
}
.eye:hover { color: var(--text); }
.eye:focus-visible { outline: 2px solid var(--accent); outline-offset: -4px; }
/* место под предупреждение появляется, только когда Caps Lock включён */
.caps { margin: 0; font-size: 12px; color: var(--warn); font-weight: 600; }
.caps.on { margin-top: 6px; }
</style>
