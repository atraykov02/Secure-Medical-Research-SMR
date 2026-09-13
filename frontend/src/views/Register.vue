<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorText } from '../api'
import { useAuthStore } from '../stores/auth'
import { ShieldCheck } from 'lucide-vue-next'
import Spinner from '../components/Spinner.vue'
import PasswordInput from '../components/PasswordInput.vue'
import { toast } from '../stores/toast'

const form = reactive({ first_name: '', last_name: '', email: '', password: '', confirm: '' })
const busy = ref(false), error = ref('')
const router = useRouter(), auth = useAuthStore()

async function submit() {
  error.value = ''
  if (form.password !== form.confirm) {
    error.value = 'Паролите не съвпадат.'
    toast.error(error.value)
    return
  }
  busy.value = true
  try {
    await api.post('/auth/register', {
      first_name: form.first_name,
      last_name: form.last_name,
      email: form.email,
      password: form.password
    })
    await auth.login(form.email, form.password)
    toast.success('Профилът е създаден успешно. Добре дошли!')
    router.push('/')
  } catch (e) {
    error.value = errorText(e)
    toast.error(error.value)
  } finally {
    busy.value = false
  }
}

function submitButtonLabel(): string {
  if (busy.value) return 'Създаване…'
  return 'Създай профил'
}
</script>

<template>
  <div class="grid min-h-screen place-items-center bg-pine-900 p-5 sm:p-10">
    <section class="rise w-full max-w-140 rounded-2xl bg-white p-7 shadow-2xl shadow-black/30 sm:p-9">
      <p class="text-[13px] font-medium text-pine-600">Нов профил</p>
      <h1 class="mt-1 text-[26px] font-bold tracking-tight">Регистрация на изследовател</h1>
      <p class="mt-2 text-[13px] leading-relaxed text-mist">
        От тук е възможно да се регистрирате единствено с роля „Изследовател“.
        Администраторските роли се предоставят от системен администратор.
      </p>

      <form @submit.prevent="submit">
        <div class="grid gap-x-4 sm:grid-cols-2">
          <label class="field">Име<input v-model="form.first_name" required></label>
          <label class="field">Фамилия<input v-model="form.last_name" required></label>
        </div>
        <label class="field">Имейл адрес<input v-model="form.email" type="email" required autocomplete="email"></label>
        <label class="field">Парола<PasswordInput v-model="form.password" :minlength="8" required autocomplete="new-password" /></label>
        <label class="field">Повторете паролата<PasswordInput v-model="form.confirm" :minlength="8" required autocomplete="new-password" /></label>

        <div v-if="error" class="note-error">{{ error }}</div>
        <button class="btn-primary mt-1 w-full py-3" :disabled="busy">
          <Spinner v-if="busy" :size="16" />
          {{ submitButtonLabel() }}
        </button>
      </form>

      <RouterLink class="mt-5 block text-center text-xs font-semibold text-pine-600 hover:text-pine-700" to="/login">
        Обратно към страницата за вход
      </RouterLink>
    </section>
  </div>
</template>
