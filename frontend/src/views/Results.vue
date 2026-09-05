<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { api } from '../api'
import type { Study } from '../types'
import { PageHead } from '../components/Ui.vue'
import { tr, date } from '../i18n'
import Spinner from '../components/Spinner.vue'
import ResultsArt from '../components/art/ResultsArt.vue'
import { ArrowUpRight, ChartNoAxesCombined, Users, ShieldCheck } from 'lucide-vue-next'

const studies = ref<Study[]>([])
const loading = ref(true)
onMounted(async () => {
  try { studies.value = (await api.get('/studies')).data }
  finally { loading.value = false }
})
const rows = computed(() => studies.value.filter(s => s.result))
function primaryResult(study: Study) {
  const r = study.result
  if (!r) return '—'
  if (study.analysis_type === 'VARIANT_FREQUENCY') return `${Number(r.frequency_percent).toFixed(2)}%`
  if (study.analysis_type === 'ALLELE_FREQUENCY') return `${Number(r.allele_frequency_percent).toFixed(2)}%`
  if (study.analysis_type === 'COHORT_MEAN_AGE') return `${Number(r.mean_age).toFixed(2)} г.`
  if (study.analysis_type === 'THERAPY_RESPONSE_RATE') return `${Number(r.response_rate_percent).toFixed(2)}%`
  return `${Number(r.odds_ratio).toFixed(2)} OR`
}

function studyCardClass(study: Study): string {
  if (study.study_mode === 'DEMONSTRATION') return '!border-amber-300'
  return ''
}
</script>

<template>
  <PageHead eyebrow="Анализи" title="Резултати" />
  <div v-if="loading" class="grid place-items-center py-20 text-pine-600"><Spinner :size="30" /></div>
  <section v-else-if="rows.length" class="rise grid gap-5 md:grid-cols-2 2xl:grid-cols-3">
    <RouterLink
      v-for="study in rows"
      :key="study.id"
      :to="`/studies/${study.id}`"
      class="group metric-card min-h-64"
      :class="studyCardClass(study)"
    >
      <div class="flex items-start justify-between">
        <span class="grid size-11 place-items-center rounded-2xl bg-pine-50 text-pine-600"><ChartNoAxesCombined :size="20" /></span>
        <ArrowUpRight :size="17" class="text-mist transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-pine-600" />
      </div>
      <p class="mt-5 text-xs font-semibold text-pine-600">{{ tr(study.analysis_type) }}</p>
      <h2 class="mt-1 line-clamp-2 text-base font-bold">{{ study.name }}</h2>
      <div class="my-5">
        <strong v-if="study.result?.suppressed" class="text-2xl text-mist">Потиснат резултат</strong>
        <strong v-else class="text-4xl font-semibold tabular-nums tracking-[-.05em]">{{ primaryResult(study) }}</strong>
      </div>
      <div class="mt-auto grid grid-cols-2 gap-3 border-t border-line/70 pt-4 text-xs text-mist">
        <span class="flex items-center gap-1.5"><Users :size="14" /> {{ study.result?.cohort_size || '—' }} в целевата група</span>
        <span class="flex items-center justify-end gap-1.5"><ShieldCheck :size="14" /> {{ date(study.completed_at || study.created_at) }}</span>
      </div>
    </RouterLink>
  </section>
  <div v-else class="panel grid place-items-center gap-3 py-16 text-center"><ResultsArt class="w-40" /><p class="text-sm text-mist">Все още няма резултати.</p></div>
</template>
