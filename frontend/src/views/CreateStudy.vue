<script setup lang="ts">
import { CircleHelp, X } from 'lucide-vue-next'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorText } from '../api'
import Spinner from '../components/Spinner.vue'
import { PageHead } from '../components/Ui.vue'
import { toast } from '../stores/toast'
import type { AnalysisType, Organization } from '../types'

const orgs = ref<Organization[]>([])
const busy = ref(false)
const helpOpen = ref(false)
const router = useRouter()
const form = reactive({
  name: '', description: '', study_mode: 'SECURE', analysis_type: 'VARIANT_FREQUENCY' as AnalysisType,
  disease_code: 'DX-LUNG', variant_code: 'VAR-A', therapy_code: 'THERAPY-A',
  min_age: 18, max_age: 90, sex: '', organization_ids: [] as string[]
})
const analyses: { value: AnalysisType; label: string }[] = [
  { value: 'VARIANT_FREQUENCY', label: 'Честота на генетичен вариант' },
  { value: 'ALLELE_FREQUENCY', label: 'Алелна честота' },
  { value: 'COHORT_MEAN_AGE', label: 'Средна възраст на целевата група' },
  { value: 'THERAPY_RESPONSE_RATE', label: 'Честота на терапевтичен отговор' },
  { value: 'THERAPY_RESPONSE', label: 'Асоциация вариант – терапевтичен отговор' },
  { value: 'VARIANT_DISEASE_ASSOCIATION', label: 'Асоциация вариант – заболяване' }
]
const analysisHelp: Record<AnalysisType, { purpose: string; source: string; data: string; operations: string; result: string }> = {
  VARIANT_FREQUENCY: {
    purpose: 'Определя какъв процент от избраната целева група носи конкретен генетичен вариант.',
    source: 'Данните се взимат от локалната база данни на всяка болница – пациенти, възраст, пол, диагнози и генетични варианти. Те не се изпращат към централния координатор.',
    data: 'Всяка болница избира пациентите, които отговарят на зададените критерии. Локално се изчисляват Nᵢ – броят пациенти, и Vᵢ – броят носители на избрания вариант.',
    operations: 'Nᵢ и Vᵢ се разделят на дялове. Чрез BGW се получават общите стойности N и V, без да се разкриват локалните резултати. След реконструкцията се изчислява V / N × 100.',
    result: 'Резултатът показва общия брой пациенти, броя носители и честотата на варианта в проценти.'
  },
  ALLELE_FREQUENCY: {
    purpose: 'Определя честотата на алтернативния алел за избрания генетичен вариант в общата целева група.',
    source: 'Използват се локалните данни за пациенти, диагнози, генетични варианти и генотипа на всеки пациент за избрания вариант.',
    data: 'За всеки пациент генотипът се преобразува локално в брой алтернативни алели. Болницата изчислява Aᵢ – общия брой алтернативни алели, и Nᵢ – броя пациенти.',
    operations: 'Aᵢ и Nᵢ се разделят на дялове. Чрез BGW се получават общите стойности A и N, без да се разкриват локалните резултати. След реконструкцията се изчислява A / (2 × N) × 100.',
    result: 'Резултатът показва общия брой пациенти, общия брой алтернативни алели и алелната честота в проценти.'
  },
  COHORT_MEAN_AGE: {
    purpose: 'Определя средната възраст на пациентите, които отговарят на зададените критерии.',
    source: 'Използват се само локалните данни за пациентите и зададените критерии за подбор. Индивидуални данни не се изпращат извън болницата.',
    data: 'След локалното филтриране всяка болница изчислява Sᵢ – сумата на възрастите, и Nᵢ – броя на избраните пациенти.',
    operations: 'Sᵢ и Nᵢ се разделят на дялове. Чрез BGW се получават общите стойности S и N, без да се разкриват локалните резултати. След реконструкцията средната възраст се изчислява като S / N.',
    result: 'Резултатът показва общия брой пациенти и средната възраст на избраната целева група.'
  },
  THERAPY_RESPONSE_RATE: {
    purpose: 'Определя какъв процент от пациентите показват положителен отговор към избраната терапия.',
    source: 'Използват се локалните данни за пациенти, приложени терапии, проведени лечения и резултатите от тях.',
    data: 'Всяка болница изчислява Nᵢ – броя пациенти, лекувани с избраната терапия, и Rᵢ – броя пациенти с положителен терапевтичен отговор.',
    operations: 'Rᵢ и Nᵢ се разделят на дялове. Чрез BGW се получават общите стойности R и N, без да се разкриват локалните резултати. След реконструкцията се изчислява R / N × 100.',
    result: 'Резултатът показва общия брой лекувани пациенти, броя пациенти с положителен отговор и честотата на терапевтичния отговор в проценти.'
  },
  THERAPY_RESPONSE: {
    purpose: 'Проверява връзката между наличието на избран генетичен вариант и отговора към конкретна терапия.',
    source: 'Използват се локалните данни за пациенти, генетични варианти, лечения, терапии и резултатите от тях.',
    data: 'Всяка болница изчислява локално стойностите A, B, C и D според това дали пациентът носи варианта и дали има положителен терапевтичен отговор.',
    operations: 'Стойностите A, B, C и D се разделят на дялове и се сумират чрез BGW. След това се изчисляват A × D и B × C. След реконструкцията odds ratio се определя като (A × D) / (B × C).',
    result: 'Резултатът показва размера на общата целева група и стойността на odds ratio, без да се разкриват локалните стойности на отделните болници.'
  },
  VARIANT_DISEASE_ASSOCIATION: {
    purpose: 'Проверява връзката между наличието на избран генетичен вариант и конкретно заболяване.',
    source: 'Използват се локалните данни за пациенти, диагнози, генетични варианти и генотипи.',
    data: 'Всяка болница изчислява локално стойностите A, B, C и D според това дали пациентът носи варианта и дали е диагностициран с избраното заболяване.',
    operations: 'Стойностите A, B, C и D се разделят на дялове и се сумират чрез BGW. След това се изчисляват A × D и B × C. След реконструкцията odds ratio се определя като (A × D) / (B × C).',
    result: 'Резултатът показва размера на общата целева група и стойността на odds ratio, без да се разкриват локалните стойности на отделните болници.'
  }
}
const selectedHelp = computed(() => analysisHelp[form.analysis_type])
const eligible = computed(() => orgs.value.filter(o => o.is_active && o.node_url))
const needsVariant = computed(() => ['VARIANT_FREQUENCY', 'ALLELE_FREQUENCY', 'THERAPY_RESPONSE', 'VARIANT_DISEASE_ASSOCIATION'].includes(form.analysis_type))
const showsVariant = computed(() => true)
const needsTherapy = computed(() => ['THERAPY_RESPONSE_RATE', 'THERAPY_RESPONSE'].includes(form.analysis_type))
const showsTherapy = computed(() => ['COHORT_MEAN_AGE', 'THERAPY_RESPONSE_RATE', 'THERAPY_RESPONSE'].includes(form.analysis_type))
const needsDisease = computed(() => form.analysis_type === 'VARIANT_DISEASE_ASSOCIATION')
const selectedRole = (organizationId: string) => form.organization_ids.indexOf(organizationId) + 1
const selectedThreshold = computed(() => Math.floor((form.organization_ids.length - 1) / 2))
const hasValidParticipantCount = computed(() => form.organization_ids.length >= 3 && form.organization_ids.length <= 6)

function studyModeCardClass(mode: string): string {
  if (form.study_mode !== mode) return 'border-line'
  if (mode === 'DEMONSTRATION') return 'border-amber-300 bg-amber-50'
  return 'border-pine-500 bg-pine-50'
}

function studyModeAccentClass(mode: string): string {
  if (mode === 'DEMONSTRATION') return 'accent-amber-600'
  return 'accent-pine-600'
}

function studyModeTitle(mode: string): string {
  if (mode === 'SECURE') return 'Режим на сигурно изчисление'
  return 'Демонстрационен режим'
}

function studyModeDescription(mode: string): string {
  if (mode === 'SECURE') return 'Само резултат от BGW протокола'
  return 'Сравнение на данни с и без BGW протокола'
}

onMounted(async () => {
  orgs.value = (await api.get('/organizations')).data
  form.organization_ids = eligible.value.slice(0, 3).map(o => o.id)
})

async function submit() {
  busy.value = true
  try {
    const { data } = await api.post('/studies', {
      name: form.name, description: form.description || null,
      analysis_type: form.analysis_type, study_mode: form.study_mode,
      organization_ids: form.organization_ids,
      criteria: {
        min_age: form.min_age, max_age: form.max_age, sex: form.sex || null,
        disease_code: form.disease_code || null,
        variant_code: showsVariant.value ? form.variant_code || null : null,
        therapy_code: showsTherapy.value ? form.therapy_code || null : null
      }
    })
    toast.success('Проучването е създадено.')
    await router.push(`/studies/${data.id}`)
  } catch (e) { toast.error(errorText(e)) }
  finally { busy.value = false }
}
</script>

<template>
  <PageHead eyebrow="Нов анализ" title="Създаване на проучване" description="Всяка болница определя целевата група локално." />
  <form class="grid max-w-4xl gap-4" @submit.prevent="submit">
    <section class="panel p-6">
      <h2 class="font-bold">1 · Информация</h2>
      <label class="field">Име<input v-model="form.name" required minlength="3"></label>
      <label class="field">Описание<textarea v-model="form.description" rows="3" /></label>
      <div class="mt-4 grid gap-3 sm:grid-cols-2">
        <label v-for="mode in ['SECURE', 'DEMONSTRATION']" :key="mode"
          class="flex cursor-pointer items-start gap-3 rounded-xl border p-4 text-left"
          :class="studyModeCardClass(mode)">
          <input v-model="form.study_mode" type="radio" :value="mode" class="mt-1 !size-4 shrink-0" :class="studyModeAccentClass(mode)">
          <span class="min-w-0 text-left">
            <b class="block text-sm">{{ studyModeTitle(mode) }}</b>
            <small class="mt-1 block text-xs text-mist">{{ studyModeDescription(mode) }}</small>
          </span>
        </label>
      </div>
    </section>

    <section class="panel p-6">
      <h2 class="mb-4 font-bold">2 · Анализ и целева група</h2>
      <label class="field !mt-0">Тип анализ
        <select v-model="form.analysis_type">
          <option v-for="analysis in analyses" :key="analysis.value" :value="analysis.value">{{ analysis.label }}</option>
        </select>
      </label>
      <button type="button" class="btn-secondary mt-2" @click="helpOpen = true">
        <CircleHelp :size="17" />Информация за анализа
      </button>
      <div class="mt-2 grid gap-x-4 sm:grid-cols-2">
        <label class="field"><span>Заболяване <small v-if="!needsDisease">(по избор)</small></span><input v-model="form.disease_code" :required="needsDisease"></label>
        <label v-if="showsVariant" class="field"><span>Вариант <small v-if="!needsVariant">(по избор)</small></span><input v-model="form.variant_code" :required="needsVariant"></label>
        <label v-if="showsTherapy" class="field"><span>Терапия <small v-if="!needsTherapy">(по избор)</small></span><input v-model="form.therapy_code" :required="needsTherapy"></label>
        <label class="field">Пол<select v-model="form.sex"><option value="">Всички</option><option value="F">Жени</option><option value="M">Мъже</option></select></label>
        <label class="field">Минимална възраст<input v-model.number="form.min_age" type="number" min="0" max="130"></label>
        <label class="field">Максимална възраст<input v-model.number="form.max_age" type="number" min="0" max="130"></label>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="helpOpen" class="fixed inset-0 z-50 grid place-items-center bg-pine-950/55 p-4 backdrop-blur-sm"
        role="presentation" @click.self="helpOpen = false" @keydown.esc="helpOpen = false">
        <section role="dialog" aria-modal="true" aria-labelledby="analysis-help-title"
          class="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
          <header class="sticky top-0 flex items-start justify-between gap-4 border-b border-line bg-white px-6 py-5">
            <div class="flex gap-3"><span class="grid size-10 shrink-0 place-items-center rounded-xl bg-pine-50 text-pine-700"><CircleHelp :size="21" /></span>
              <div><span class="text-xs font-semibold text-pine-600">Информация за избрания анализ</span><h2 id="analysis-help-title" class="mt-1 text-lg font-bold">{{ analyses.find(x => x.value === form.analysis_type)?.label }}</h2></div>
            </div>
            <button type="button" class="grid size-9 shrink-0 place-items-center rounded-lg text-mist transition hover:bg-paper hover:text-ink" aria-label="Затвори" @click="helpOpen = false"><X :size="20" /></button>
          </header>
          <div class="grid gap-5 p-6 text-left text-sm leading-relaxed">
            <div><h3 class="font-bold text-ink">Какъв анализ се извършва?</h3><p class="mt-1.5 text-mist">{{ selectedHelp.purpose }}</p></div>
            <div><h3 class="font-bold text-ink">Откъде се взимат данните?</h3><p class="mt-1.5 text-mist">{{ selectedHelp.source }}</p></div>
            <div><h3 class="font-bold text-ink">Какви данни се подготвят?</h3><p class="mt-1.5 text-mist">{{ selectedHelp.data }}</p></div>
            <div><h3 class="font-bold text-ink">Какви операции се извършват?</h3><p class="mt-1.5 text-mist">{{ selectedHelp.operations }}</p></div>
            <div><h3 class="font-bold text-ink">Какъв резултат се очаква?</h3><p class="mt-1.5 text-mist">{{ selectedHelp.result }}</p></div>
            <aside class="rounded-xl border border-pine-100 bg-pine-50 p-4 text-xs text-pine-800"><b>Защита на данните:</b> Индивидуалните пациентски записи и локално изчислените стойности остават видими само в съответната болница и не се изпращат към централния координатор. Между отделните възли се обменят единствено дялове, а след приключване на изчислението координаторът получава само крайния резултат.</aside>
          </div>
        </section>
      </div>
    </Teleport>

    <section class="panel p-6">
      <h2 class="font-bold">3 · Участващи организации</h2>
      <p class="mt-1 text-xs text-mist">Изберете между 3 и 6 болници. Поредността на участие P1–Pn на всяка болница се определя според реда на избиране.</p>
      <div v-if="form.organization_ids.length" class="mt-3 rounded-lg border border-line bg-paper px-4 py-3 text-xs">
        Избрани участници: <b>n = {{ form.organization_ids.length }}</b>
        <span v-if="hasValidParticipantCount"> · Автоматичен праг на споделяне: <b>t = {{ selectedThreshold }}</b></span>
        <span v-else class="text-amber-700"> · Необходими са поне 3 болници</span>
      </div>
      <label v-for="organization in eligible" :key="organization.id"
        class="mt-3 flex cursor-pointer items-center justify-start gap-3 rounded-lg border border-line p-3 text-left has-checked:border-pine-400 has-checked:bg-pine-50/50">
        <input v-model="form.organization_ids" type="checkbox" :value="organization.id"
          class="!size-4 shrink-0 accent-pine-600"
          :disabled="form.organization_ids.length >= 6 && !form.organization_ids.includes(organization.id)">
        <span class="min-w-0 grow text-left">
          <b class="block text-[13px]">{{ organization.name }}</b>
          <small class="mt-0.5 block text-xs text-mist">
            Възел {{ organization.participant_index }}
            <template v-if="selectedRole(organization.id)"> · BGW участник P{{ selectedRole(organization.id) }}</template>
          </small>
        </span>
      </label>
    </section>
    <div class="flex justify-end gap-2">
      <RouterLink class="btn-secondary" to="/studies">Отказ</RouterLink>
      <button class="btn-primary" :disabled="busy || !hasValidParticipantCount"><Spinner v-if="busy" :size="16" />Създай и покани</button>
    </div>
  </form>
</template>
