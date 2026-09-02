<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { api } from '../api'
import type { Study, MPCSession, Organization } from '../types'
import { StatusBadge } from '../components/Ui.vue'
import Spinner from '../components/Spinner.vue'
import EmptyArt from '../components/art/EmptyArt.vue'
import { useAuthStore } from '../stores/auth'
import { date, tr } from '../i18n'
import { ArrowUpRight, Plus, FlaskConical, Building2, CircleCheckBig, Clock3, Activity, ShieldCheck } from 'lucide-vue-next'

const auth = useAuthStore()
const studies = ref<Study[]>([])
const sessions = ref<MPCSession[]>([])
const orgs = ref<Organization[]>([])
const loading = ref(true)
onMounted(async () => {
  try {
    [studies.value, sessions.value, orgs.value] = await Promise.all([
      api.get('/studies').then(r => r.data),
      api.get('/mpc-sessions').then(r => r.data),
      api.get('/organizations').then(r => r.data)
    ])
  } finally { loading.value = false }
})
const activeCount = computed(() => studies.value.filter(s => !['COMPLETED', 'FAILED'].includes(s.status)).length)
const waitingCount = computed(() => studies.value.filter(s => s.status === 'WAITING_APPROVAL').length)
const completedCount = computed(() => studies.value.filter(s => s.status === 'COMPLETED').length)
const completionRate = computed(() => studies.value.length ? Math.round(completedCount.value / studies.value.length * 100) : 0)
const welcomeName = computed(() => {
  if (auth.user?.role === 'SYSTEM_ADMIN') return 'Системен администратор'
  if (auth.user?.role === 'ORG_ADMIN') {
    return orgs.value.find(org => org.id === auth.user?.organization_id)?.name || ''
  }
  return auth.user?.first_name || ''
})
const stats = computed(() => [
  { label: 'Активни проучвания', value: activeCount.value, icon: Activity, tone: 'bg-pine-600 text-white', iconTone: 'bg-white/15' },
  { label: 'Изчакват одобрение', value: waitingCount.value, icon: Clock3, tone: 'bg-[#dff0e8] text-pine-900', iconTone: 'bg-pine-600/10 text-pine-700' },
  { label: 'Завършени', value: completedCount.value, icon: CircleCheckBig, tone: 'bg-[#f4e9df] text-[#64351f]', iconTone: 'bg-clay/10 text-clay' },
  { label: 'Организации', value: orgs.value.length, icon: Building2, tone: 'bg-white text-ink', iconTone: 'bg-pine-50 text-pine-600' }
])

function statValue(value: number): number | string {
  if (loading.value) return '—'
  return value
}
</script>

<template>
  <div class="pb-24 xl:pb-0">
    <header class="rise mb-7 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p class="mb-2 text-xs font-semibold uppercase tracking-[.18em] text-pine-600">Начален екран</p>
        <div v-if="auth.user?.role === 'ORG_ADMIN' && !welcomeName" class="h-10 w-80 max-w-full animate-pulse rounded-xl bg-pine-100" aria-label="Зареждане на името на организацията"></div>
        <h1 v-else class="text-3xl font-bold tracking-[-.04em] sm:text-4xl">Добре дошли, {{ welcomeName }}</h1>
        <p class="mt-2 text-sm text-mist">Актуално състояние на проучванията и MPC сесиите в системата.</p>
      </div>
      <RouterLink v-if="auth.user?.role !== 'ORG_ADMIN'" to="/studies/new" class="btn-primary"><Plus :size="17" /> Ново проучване</RouterLink>
    </header>

    <section class="rise grid gap-4 sm:grid-cols-2 2xl:grid-cols-4" style="animation-delay:.06s">
      <article v-for="item in stats" :key="item.label" class="metric-card" :class="item.tone">
        <div class="flex items-start justify-between">
          <span class="text-xs font-medium opacity-75">{{ item.label }}</span>
          <span class="grid size-9 place-items-center rounded-xl" :class="item.iconTone"><component :is="item.icon" :size="17" /></span>
        </div>
        <strong class="mt-5 block text-4xl font-semibold tabular-nums tracking-[-.06em]">{{ statValue(item.value) }}</strong>
        <span class="mt-2 block text-[11px] opacity-60">в текущото работно пространство</span>
      </article>
    </section>

    <section class="mt-5 grid gap-5 2xl:grid-cols-[1.55fr_.75fr]">
      <article class="panel rise overflow-hidden" style="animation-delay:.12s">
        <div class="flex items-center justify-between border-b border-line/70 px-5 py-4 sm:px-6">
          <div><h2 class="section-title">Последни проучвания</h2><p class="mt-1 text-xs text-mist">Най-скорошната активност</p></div>
          <RouterLink to="/studies" class="flex items-center gap-1 text-xs font-semibold text-pine-600">Виж всички <ArrowUpRight :size="14" /></RouterLink>
        </div>
        <div v-if="loading" class="grid place-items-center py-16 text-pine-600"><Spinner :size="28" /></div>
        <div v-else-if="!studies.length" class="grid place-items-center gap-3 py-14 text-center"><EmptyArt class="w-32" /><p class="text-sm text-mist">Все още няма проучвания.</p></div>
        <div v-else class="divide-y divide-line/60 px-5 sm:px-6">
          <RouterLink v-for="study in studies.slice(0, 5)" :key="study.id" :to="`/studies/${study.id}`" class="group flex items-center gap-4 py-4">
            <span class="grid size-10 shrink-0 place-items-center rounded-xl bg-pine-50 text-pine-600"><FlaskConical :size="18" /></span>
            <div class="min-w-0 grow"><b class="block truncate text-sm">{{ study.name }}</b><span class="mt-1 block truncate text-xs text-mist">{{ tr(study.analysis_type) }} · {{ date(study.created_at) }}</span></div>
            <StatusBadge :value="study.status" />
            <ArrowUpRight :size="15" class="hidden text-mist transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5 sm:block" />
          </RouterLink>
        </div>
      </article>

      <div class="grid gap-5">
        <article class="panel rise p-6" style="animation-delay:.18s">
          <div class="flex items-start justify-between"><div><h2 class="section-title">Напредък</h2><p class="mt-1 text-xs text-mist">Завършени проучвания</p></div><CircleCheckBig :size="20" class="text-pine-600" /></div>
          <div class="mt-6 flex items-center gap-5">
            <div class="grid size-24 shrink-0 place-items-center rounded-full" :style="{ background: `conic-gradient(#1f6f58 ${completionRate * 3.6}deg, #e6ece8 0)` }">
              <div class="grid size-18 place-items-center rounded-full bg-white"><strong class="text-xl">{{ completionRate }}%</strong></div>
            </div>
            <div class="space-y-2 text-xs text-mist"><p><b class="text-ink">{{ completedCount }}</b> завършени</p><p><b class="text-ink">{{ activeCount }}</b> активни</p><p><b class="text-ink">{{ studies.length }}</b> общо</p></div>
          </div>
        </article>
        <article class="rise overflow-hidden rounded-2xl bg-pine-900 p-6 text-white shadow-[0_14px_35px_rgba(13,37,31,.18)]" style="animation-delay:.24s">
          <div class="flex items-start justify-between"><div><h2 class="section-title">Параметри на протокола</h2><p class="mt-1 text-xs text-pine-300">Протокол BGW - конфигурация</p></div><ShieldCheck :size="21" class="text-pine-300" /></div>
          <div class="mt-7 grid grid-cols-3 gap-3 text-center"><div><b class="block text-xl">3-6</b><small class="text-pine-300">участници</small></div><div><b class="block text-xl">1-2</b><small class="text-pine-300">праг</small></div><div><b class="block text-xl">{{ sessions.length }}</b><small class="text-pine-300">сесии</small></div></div>
        </article>
      </div>
    </section>
  </div>
</template>
