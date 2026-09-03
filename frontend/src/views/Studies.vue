<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { api } from '../api'
import type { Study } from '../types'
import { PageHead, StatusBadge } from '../components/Ui.vue'
import { useAuthStore } from '../stores/auth'
import { tr, date } from '../i18n'
import Spinner from '../components/Spinner.vue'
import EmptyArt from '../components/art/EmptyArt.vue'
import { Plus, Search, ArrowUpRight, Users, FlaskConical } from 'lucide-vue-next'

const rows = ref<Study[]>([]), q = ref(''), a = useAuthStore()
const loading = ref(true)
onMounted(async () => {
  try { rows.value = (await api.get('/studies')).data }
  finally { loading.value = false }
})
const shown = computed(() => rows.value.filter(s => s.name.toLowerCase().includes(q.value.toLowerCase())))

function studyCardClass(study: Study): string {
  if (study.study_mode === 'DEMONSTRATION') return '!border-amber-300'
  return ''
}
</script>

<template>
  <PageHead eyebrow="Работно пространство" title="Проучвания">
    <RouterLink v-if="a.user?.role !== 'ORG_ADMIN'" class="btn-primary" to="/studies/new"><Plus :size="17" /> Ново проучване</RouterLink>
  </PageHead>

  <div class="panel mb-5 flex items-center gap-3 p-3">
    <label class="flex h-11 grow items-center gap-2 rounded-xl bg-paper/80 px-3 text-mist">
      <Search :size="17" /><input v-model="q" placeholder="Търсене по име…" class="!border-0 !bg-transparent !p-0 !ring-0">
    </label>
    <span class="hidden rounded-xl bg-pine-50 px-4 py-3 text-xs font-semibold text-pine-700 sm:block">{{ shown.length }} проучвания</span>
  </div>

  <div v-if="loading" class="grid place-items-center py-20 text-pine-600"><Spinner :size="30" /></div>
  <div v-else-if="!shown.length" class="panel grid place-items-center gap-3 py-16 text-center"><EmptyArt class="w-40" /><p class="text-sm text-mist">Няма открити проучвания.</p></div>
  <section v-else class="rise grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
    <RouterLink v-for="study in shown" :key="study.id" :to="`/studies/${study.id}`"
      class="group metric-card flex min-h-56 flex-col"
      :class="studyCardClass(study)">
      <div class="flex items-start justify-between gap-3">
        <span class="grid size-11 place-items-center rounded-2xl bg-pine-50 text-pine-600"><FlaskConical :size="20" /></span>
        <StatusBadge :value="study.status" />
      </div>
      <div class="mt-5">
        <h2 class="line-clamp-2 text-lg font-bold leading-snug tracking-tight">{{ study.name }}</h2>
        <p class="mt-2 text-xs font-medium text-pine-600">{{ tr(study.analysis_type) }}</p>
      </div>
      <div class="mt-auto flex items-end justify-between border-t border-line/70 pt-4">
        <div><span class="flex items-center gap-1.5 text-xs text-mist"><Users :size="14" /> {{ study.participants.length }} участници</span><time class="mt-1 block text-[11px] text-mist">{{ date(study.created_at) }}</time></div>
        <span class="grid size-9 place-items-center rounded-full bg-paper text-mist transition group-hover:bg-pine-600 group-hover:text-white"><ArrowUpRight :size="16" /></span>
      </div>
    </RouterLink>
  </section>
</template>
