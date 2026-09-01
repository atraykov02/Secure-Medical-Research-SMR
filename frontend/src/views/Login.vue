<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { errorText } from '../api'
import { ShieldCheck, Network } from 'lucide-vue-next'
import Spinner from '../components/Spinner.vue'
import { toast } from '../stores/toast'
import logoUrl from '../components/logo.png'

const email = ref('researcher@precisionmpc.example.com')
const password = ref('Research123!')
const busy = ref(false), error = ref('')
const a = useAuthStore(), router = useRouter()

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await a.login(email.value, password.value)
    toast.success('Успешен вход. Добре дошли в Secure Medical Research.')
    router.push('/')
  } catch (e) {
    error.value = errorText(e)
    toast.error(error.value)
  } finally {
    busy.value = false
  }
}

function submitButtonLabel(): string {
  if (busy.value) return 'Влизане…'
  return 'Вход в системата'
}
</script>

<template>
  <div class="grid min-h-screen lg:grid-cols-[1.1fr_0.9fr]">
    <section class="relative flex flex-col justify-between overflow-hidden bg-pine-900 p-8 text-white max-lg:min-h-105 lg:p-12">
      <div class="flex items-center gap-3">
        <img :src="logoUrl" alt="Secure Medical Research" class="size-9 shrink-0 object-contain">
        <strong class="text-[15px] font-bold">Secure Medical Research</strong>
      </div>

      <div class="relative z-10 max-w-xl py-10">
        <h1 class="text-4xl font-bold leading-[1.12] tracking-tight lg:text-[52px]">
          Извършвайте сигурни проучвания. Запазете данните на пациентите поверителни.
        </h1>
        <p class="mt-5 max-w-md leading-relaxed text-pine-200">
          Анализ на медицински данни, базиран на протокола за сигурни многостранни изчисления BGW.
          Данните на пациентите остават поверителни.
        </p>
      </div>

      <svg class="pointer-events-none absolute -bottom-6 -right-10 w-130 max-w-[85%] text-pine-300/60" viewBox="0 0 520 240" fill="none" aria-hidden="true">
        <path class="draw-line" d="M0 218 C 120 214, 220 190, 300 140 S 460 20, 520 -10" stroke="currentColor" stroke-width="1.5" />
        <g fill="#8cbaa5">
          <circle cx="150" cy="207" r="5" />
          <circle cx="300" cy="140" r="5" />
          <circle cx="432" cy="46" r="5" />
        </g>
        <g fill="currentColor" font-size="12" font-family="IBM Plex Mono, monospace">
          <text x="140" y="192">f(1)</text>
          <text x="290" y="125">f(2)</text>
          <text x="422" y="31">f(3)</text>
        </g>
      </svg>

      <div class="relative z-10 flex flex-col gap-2.5 text-[13px] text-pine-200 sm:flex-row sm:gap-8">
        <span class="flex items-center gap-2"><ShieldCheck :size="17" />Сигурност на данните при получестен модел</span>
        <span class="flex items-center gap-2"><Network :size="17" />6 организации</span>
      </div>
    </section>

    <section class="grid place-items-center bg-paper p-8">
      <form class="rise w-full max-w-95" @submit.prevent="submit">
        <h2 class="text-[26px] font-bold tracking-tight">Добре дошли</h2>
        <p class="mb-7 mt-1 text-sm text-mist">Влезте в системата за сигурни проучвания.</p>

        <label class="field">Имейл адрес
          <input v-model="email" type="email" required autocomplete="username">
        </label>
        <label class="field">Парола
          <input v-model="password" type="password" required autocomplete="current-password">
        </label>

        <div v-if="error" class="note-error">{{ error }}</div>

        <button class="btn-primary w-full py-3" :disabled="busy">
          <Spinner v-if="busy" :size="16" />
          {{ submitButtonLabel() }}
        </button>

        <small class="mt-4 block text-center text-xs text-mist">
          Нямате профил?
          <RouterLink to="/register" class="font-semibold text-pine-600 hover:text-pine-700">Регистрирайте се като изследовател</RouterLink>
        </small>
      </form>
    </section>
  </div>
</template>
