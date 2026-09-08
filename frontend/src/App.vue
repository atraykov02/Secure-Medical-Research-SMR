<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { tr } from './i18n'
import Toaster from './components/Toaster.vue'
import AmbientBackground from './components/AmbientBackground.vue'
import Spinner from './components/Spinner.vue'
import { toast } from './stores/toast'
import { LayoutDashboard, FlaskConical, Plus, Network, ChartNoAxesCombined, ScrollText, LogOut, Settings, Building2 } from 'lucide-vue-next'
import logoUrl from './components/logo.png'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const groups = computed<any[]>(() => [
  { label: '', items: [{ to: '/', label: 'Табло', icon: LayoutDashboard }] },
  { label: 'Проучвания', items: [
    { to: '/studies', label: 'Всички проучвания', icon: FlaskConical },
    { to: '/studies/new', label: 'Ново проучване', icon: Plus, roles: ['RESEARCHER', 'SYSTEM_ADMIN'] }
  ] },
  { label: 'Изпълнение', items: [
    { to: '/sessions', label: 'MPC сесии', icon: Network },
    { to: '/results', label: 'Резултати', icon: ChartNoAxesCombined }
  ] },
  { label: 'Организация', items: [
    { to: '/organization', label: 'Моята организация', icon: Building2, roles: ['ORG_ADMIN'] }
  ] },
  { label: 'Контрол', items: [
    { to: '/audit', label: 'История на действията', icon: ScrollText },
    { to: '/administration', label: 'Администрация', icon: Settings, roles: ['SYSTEM_ADMIN'] }
  ] }
  ]
    .map(group => ({ ...group, items: group.items.filter(item => !item.roles || item.roles.includes(auth.user?.role || '')) }))
    .filter(group => group.items.length))
const items = computed(() => groups.value.flatMap(group => group.items))

function logout() {
  auth.logout()
  toast.info('Излязохте успешно от системата.')
  router.push('/login')
}
</script>

<template>
  <router-view v-if="route.meta.public" />
  <div v-else-if="!auth.ready" class="grid min-h-screen place-items-center bg-pine-900 text-pine-200" aria-label="Зареждане на потребителската сесия">
    <Spinner :size="30" />
  </div>
  <div v-else class="min-h-screen xl:pl-72">
    <AmbientBackground />
    <main class="min-h-screen px-5 py-7 sm:px-9 lg:px-14 lg:py-10">
      <div class="mx-auto max-w-6xl">
        <router-view v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <div :key="route.fullPath">
              <component :is="Component" />
            </div>
          </Transition>
        </router-view>
      </div>
    </main>

    <aside class="fixed inset-y-0 left-0 z-40 hidden w-72 flex-col overflow-hidden bg-pine-900 text-white xl:flex">
      <div class="flex items-center gap-3 px-7 pb-7 pt-8">
        <img :src="logoUrl" alt="Secure Medical Research" class="size-10 shrink-0 object-contain">
        <div>
          <strong class="block text-[15px] tracking-tight">Secure Medical Research</strong>
          <span class="text-[10px] uppercase tracking-[.18em] text-pine-300">research network</span>
        </div>
      </div>

      <div class="mx-7 h-px bg-pine-700/70"></div>
      <nav class="mt-5 grid gap-4 overflow-y-auto px-4 pb-4">
        <section v-for="group in groups" :key="group.label || 'main'">
          <h2 v-if="group.label" class="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[.16em] text-pine-400">{{ group.label }}</h2>
          <div class="grid gap-1">
            <RouterLink v-for="item in group.items" :key="item.to" :to="item.to" class="nav-right">
              <component :is="item.icon" :size="17" /><span>{{ item.label }}</span><i></i>
            </RouterLink>
          </div>
        </section>
      </nav>

      <div class="mx-7 mt-auto h-px bg-pine-700/70"></div>
      <div class="flex items-center gap-3 px-7 py-6">
        <div class="grid size-9 place-items-center rounded-full bg-pine-700 text-[11px] font-bold">
          {{ auth.user?.first_name[0] }}{{ auth.user?.last_name[0] }}
        </div>
        <div class="min-w-0 grow leading-tight">
          <b class="block truncate text-xs">{{ auth.user?.first_name }} {{ auth.user?.last_name }}</b>
          <small class="block truncate text-[10px] text-pine-300">{{ tr(auth.user?.role) }}</small>
        </div>
        <button class="rounded-full p-2 text-pine-300 transition hover:bg-white/10 hover:text-white" title="Изход" @click="logout">
          <LogOut :size="16" />
        </button>
      </div>
    </aside>

    <nav class="fixed inset-x-3 bottom-3 z-40 flex items-center justify-around overflow-x-auto rounded-2xl bg-pine-900 px-2 py-2 text-white shadow-2xl xl:hidden">
      <RouterLink v-for="item in items" :key="item.to" :to="item.to" class="nav-mobile" :title="item.label">
        <component :is="item.icon" :size="19" />
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>
  </div>
  <Toaster />
</template>
