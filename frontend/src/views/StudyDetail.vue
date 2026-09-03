<script setup lang="ts">
import { Check, Lightbulb, Play, ShieldCheck, X } from 'lucide-vue-next'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, errorText } from '../api'
import Spinner from '../components/Spinner.vue'
import { PageHead, StatusBadge } from '../components/Ui.vue'
import { dateTime, tr } from '../i18n'
import { getLocalStudyInput } from '../localNode'
import { useAuthStore } from '../stores/auth'
import { toast } from '../stores/toast'
import type { Audit, LocalStudyInput, MPCSession, Study, Verification } from '../types'

const route = useRoute(), a = useAuthStore()
const study = ref<Study>(), sessions = ref<MPCSession[]>([]), audit = ref<Audit[]>([])
const localInput = ref<LocalStudyInput>()
const verification = ref<Verification>()
const verifying = ref(false)
const busy = ref(false)
type StudyTab = 'overview' | 'participants' | 'verification' | 'history'
const activeTab = ref<StudyTab>('overview')
const studyTabs: { value: StudyTab; label: string }[] = [
  { value: 'overview', label: 'Преглед' },
  { value: 'participants', label: 'Участници' },
  { value: 'verification', label: 'Проверка' },
  { value: 'history', label: 'История на действията' }
]
const verificationOverviewSteps = [
  {
    number: '1',
    title: 'Локален подбор на данни',
    description: 'Всяка болница филтрира собствените си пациенти по показаните критерии.',
    cardClass: 'border-pine-100 bg-pine-50/45',
    badgeClass: 'bg-pine-300 text-pine-900',
    titleClass: 'text-pine-800'
  },
  {
    number: '2',
    title: 'Локални изчисления',
    description: 'Изчисляват се само необходимите стойности; индивидуални записи не участват в обмена на данни между участниците.',
    cardClass: 'border-pine-200 bg-pine-50/70',
    badgeClass: 'bg-pine-400 text-white',
    titleClass: 'text-pine-800'
  },
  {
    number: '3',
    title: 'Изчисление с помощта на BGW',
    description: 'Изчислените локални стойности се превръщат в дялове и се обработват съвместно от всички участващи болници.',
    cardClass: 'border-pine-300 bg-pine-100/55',
    badgeClass: 'bg-pine-500 text-white',
    titleClass: 'text-pine-900'
  },
  {
    number: '4',
    title: 'Независима проверка',
    description: 'Същите входни данни се пресмятат отделно в явен вид и се сравняват с BGW.',
    cardClass: 'border-pine-400 bg-pine-100/80',
    badgeClass: 'bg-pine-700 text-white',
    titleClass: 'text-pine-900'
  }
] as const

const phases = ['Локален избор на целева група', 'Споделяне на входни данни', 'Разпределяне на дяловете', 'Сигурно изчисление', 'Реконструкция на резултата']

async function load() {
  const id = route.params.id
  ;[study.value, sessions.value, audit.value] = await Promise.all([
    api.get(`/studies/${id}`).then(r => r.data),
    api.get(`/mpc-sessions?study_id=${id}`).then(r => r.data),
    api.get(`/audit?study_id=${id}`).then(r => r.data)
  ])
  if (a.user?.role === 'ORG_ADMIN' && study.value) {
    try { localInput.value = await getLocalStudyInput(study.value) }
    catch { localInput.value = undefined }
  }
}
onMounted(load)

const timer = setInterval(() => { if (study.value?.status === 'COMPUTING') load() }, 2500)
onUnmounted(() => clearInterval(timer))

const myParticipant = computed(() => study.value?.participants.find(p => p.organization_id === a.user?.organization_id))
const canRun = computed(() => study.value?.status === 'READY' || (
  study.value?.status === 'FAILED' && study.value.participants.every(p => p.status === 'APPROVED')
))

function associationSubject(currentStudy: Study): string {
  if (currentStudy.analysis_type === 'THERAPY_RESPONSE') {
    return `положителен отговор към ${currentStudy.criteria.therapy_code || 'избраната терапия'}`
  }
  return `наличие на заболяване ${currentStudy.criteria.disease_code || ''}`
}

function associationDescription(oddsRatio: number, subject: string): string {
  if (oddsRatio > 1) return `по-високи шансове за ${subject}`
  if (oddsRatio < 1) return `по-ниски шансове за ${subject}`
  return `еднакви шансове за ${subject}`
}

function associationDirection(oddsRatio: number): string {
  if (oddsRatio > 1) return 'положителна'
  if (oddsRatio < 1) return 'отрицателна'
  return 'не се наблюдава'
}

function associationConclusion(direction: string): string {
  if (direction === 'не се наблюдава') {
    return 'Не се наблюдава асоциация между сравняваните фактори в изследваната целева група.'
  }
  return `Наблюдава се ${direction} асоциация в изследваната целева група. Това е статистическа зависимост и не доказва причинно-следствена връзка.`
}

const resultHeadline = computed(() => {
  const s = study.value, r = s?.result
  if (!s || !r) return ''
  if (s.analysis_type === 'VARIANT_FREQUENCY') return `${Number(r.frequency_percent).toFixed(2)}%`
  if (s.analysis_type === 'ALLELE_FREQUENCY') return `${Number(r.allele_frequency_percent).toFixed(2)}%`
  if (s.analysis_type === 'COHORT_MEAN_AGE') return `${Number(r.mean_age).toFixed(2)} години`
  if (s.analysis_type === 'THERAPY_RESPONSE_RATE') return `${Number(r.response_rate_percent).toFixed(2)}%`
  return `${Number(r.odds_ratio).toFixed(2)} OR`
})
const resultDetails = computed(() => {
  const s = study.value, r = s?.result
  if (!s || !r) return ''
  if (s.analysis_type === 'VARIANT_FREQUENCY') return `${r.variant_count} носители · обща целева група ${r.cohort_size}`
  if (s.analysis_type === 'ALLELE_FREQUENCY') return `${r.alternative_allele_count} алтернативни алела · обща целева група ${r.cohort_size}`
  if (s.analysis_type === 'THERAPY_RESPONSE_RATE') return `${r.responder_count} отговорили · ${r.treated_count} лекувани пациенти`
  return `Общ размер на целевата група: ${r.cohort_size}`
})
const resultInterpretation = computed(() => {
  const s = study.value, r = s?.result
  if (!s || !r) return null
  if (r.suppressed) return {
    interpretation: 'Резултатът не се показва, защото целевата група е под минималния праг за поверителност.',
    conclusion: 'Наличните данни не позволяват формулиране на извод за тази целева група.'
  }
  const cohort = Number(r.cohort_size ?? 0)
  if (s.analysis_type === 'VARIANT_FREQUENCY') {
    const percent = Number(r.frequency_percent).toFixed(2)
    return {
      interpretation: `Генетичният вариант ${s.criteria.variant_code || ''} е установен при ${r.variant_count} от общо ${cohort} пациенти (${percent}%) в избраната целева група.`,
      conclusion: `Вариантът присъства при ${percent}% от изследваната многоцентрова група. Резултатът описва разпространението му, но самостоятелно не доказва връзка със заболяване или приложим терапевтичен ефект.`
    }
  }
  if (s.analysis_type === 'ALLELE_FREQUENCY') {
    const percent = Number(r.allele_frequency_percent).toFixed(2)
    return {
      interpretation: `Отчетени са ${r.alternative_allele_count} алтернативни алела сред общо ${cohort * 2} възможни алела при ${cohort} пациенти.`,
      conclusion: `Алтернативният алел на вариант ${s.criteria.variant_code || ''} има честота ${percent}% в изследваната целева група.`
    }
  }
  if (s.analysis_type === 'COHORT_MEAN_AGE') {
    const age = Number(r.mean_age).toFixed(2)
    return {
      interpretation: `Средната възраст на ${cohort} пациенти, които отговарят на зададените критерии, е ${age} години.`,
      conclusion: `Резултатът характеризира възрастовия профил на общата целева група от участващите организации.`
    }
  }
  if (s.analysis_type === 'THERAPY_RESPONSE_RATE') {
    const percent = Number(r.response_rate_percent).toFixed(2)
    return {
      interpretation: `Положителен отговор е отчетен при ${r.responder_count} от ${r.treated_count ?? cohort} пациенти, лекувани с ${s.criteria.therapy_code || 'избраната терапия'} (${percent}%).`,
      conclusion: `В изследваната целева група ${percent}% от лекуваните пациенти са показали положителен терапевтичен отговор. Без контролна група резултатът не доказва самостоятелно ефективност на терапията.`
    }
  }
  const oddsRatio = r.odds_ratio == null ? null : Number(r.odds_ratio)
  if (oddsRatio == null || !Number.isFinite(oddsRatio)) return {
    interpretation: 'Отношението на шансовете не може да бъде изчислено, защото поне една от необходимите сравнителни групи няма достатъчно наблюдения.',
    conclusion: 'От тези данни не може да бъде направен извод за наличие или посока на асоциация.'
  }
  const subject = associationSubject(s)
  const association = associationDescription(oddsRatio, subject)
  const direction = associationDirection(oddsRatio)
  return {
    interpretation: `За носителите на вариант ${s.criteria.variant_code || ''} са отчетени ${association} спрямо пациентите без варианта (OR = ${oddsRatio.toFixed(2)}).`,
    conclusion: associationConclusion(direction)
  }
})
const demoMetrics = computed(() => {
  const type = study.value?.analysis_type
  if (type === 'VARIANT_FREQUENCY') return [{ key: 'cohort_size', label: 'Пациенти (Nᵢ)' }, { key: 'variant_count', label: 'Носители (Vᵢ)' }]
  if (type === 'ALLELE_FREQUENCY') return [{ key: 'cohort_size', label: 'Пациенти (Nᵢ)' }, { key: 'alternative_allele_count', label: 'Алтернативни алели (Aᵢ)' }]
  if (type === 'COHORT_MEAN_AGE') return [{ key: 'cohort_size', label: 'Пациенти (Nᵢ)' }, { key: 'age_sum', label: 'Сума на възрастите (Sᵢ)' }]
  if (type === 'THERAPY_RESPONSE_RATE') return [{ key: 'cohort_size', label: 'Лекувани (Nᵢ)' }, { key: 'responder_count', label: 'Отговорили (Rᵢ)' }]
  return [{ key: 'a', label: 'Aᵢ' }, { key: 'b', label: 'Bᵢ' }, { key: 'c', label: 'Cᵢ' }, { key: 'd', label: 'Dᵢ' }]
})
const demoCircuit = computed(() => {
  const type = study.value?.analysis_type
  if (['THERAPY_RESPONSE', 'VARIANT_DISEASE_ASSOCIATION'].includes(type || ''))
    return ['Сумиране: A=ΣAᵢ, B=ΣBᵢ, C=ΣCᵢ, D=ΣDᵢ', 'BGW - умножение: AD=A×D и BC=B×C', 'Редукция на степента на умножените дялове', 'Разрешена реконструкция на AD, BC и размера на целевата група', 'Изходна формула: OR=AD/BC']
  if (type === 'ALLELE_FREQUENCY') return ['Споделяне по схемата на  Shamir на Aᵢ и Nᵢ', 'Сумиране: A=ΣAᵢ и N=ΣNᵢ', 'Разрешена реконструкция на A и N', 'Изходна формула: A/(2×N)×100']
  if (type === 'COHORT_MEAN_AGE') return ['Споделяне по схемата на  Shamir на Sᵢ и Nᵢ', 'Сумиране: S=ΣSᵢ и N=ΣNᵢ', 'Разрешена реконструкция на S и N', 'Изходна формула извън BGW: S/N']
  if (type === 'THERAPY_RESPONSE_RATE') return ['Споделяне по схемата на  Shamir на Rᵢ и Nᵢ', 'Сумиране: R=ΣRᵢ и N=ΣNᵢ', 'Разрешена реконструкция на R и N', 'Изходна формула: R/N×100']
  return ['Споделяне по схемата на  Shamir на Vᵢ и Nᵢ', 'Сумиране: V=ΣVᵢ и N=ΣNᵢ', 'Разрешена реконструкция на V и N', 'Изходна формула: V/N×100']
})
const demoEquation = computed(() => {
  const r = verification.value?.reference
  if (!r) return ''
  const type = study.value?.analysis_type
  if (type === 'VARIANT_FREQUENCY') return `${r.variant_count} / ${r.cohort_size} × 100 = ${r.frequency_percent}%`
  if (type === 'ALLELE_FREQUENCY') return `${r.alternative_allele_count} / (2 × ${r.cohort_size}) × 100 = ${r.allele_frequency_percent}%`
  if (type === 'COHORT_MEAN_AGE') return `ΣSᵢ / ΣNᵢ = ${r.mean_age} години`
  if (type === 'THERAPY_RESPONSE_RATE') return `${r.responder_count} / ${r.cohort_size} × 100 = ${r.response_rate_percent}%`
  return `(${r.a} × ${r.d}) / (${r.b} × ${r.c}) = ${r.ad} / ${r.bc} = ${r.odds_ratio}`
})
function valuesFor(key: string): number[] {
  return (verification.value?.local_breakdown || []).map(row => Number(row[key] ?? 0))
}
function sumFormula(key: string, symbol: string): string {
  const values = valuesFor(key)
  return `${symbol} = ${values.join(' + ')} = ${values.reduce((sum, value) => sum + value, 0)}`
}
const numericTrace = computed(() => {
  if (!verification.value) return [] as { title: string; formula: string; explanation: string }[]
  const type = study.value?.analysis_type
  const rows: { title: string; formula: string; explanation: string }[] = []
  if (type === 'VARIANT_FREQUENCY') {
    rows.push({ title: 'Глобален брой пациенти', formula: sumFormula('cohort_size', 'N'), explanation: 'Сума на локалните размери на целевите групи.' })
    rows.push({ title: 'Глобален брой носители', formula: sumFormula('variant_count', 'V'), explanation: 'Сума на локалните носители.' })
  } else if (type === 'ALLELE_FREQUENCY') {
    rows.push({ title: 'Глобален брой пациенти', formula: sumFormula('cohort_size', 'N'), explanation: 'Сумата определя общо 2×N възможни алела.' })
    rows.push({ title: 'Глобален брой алтернативни алели', formula: sumFormula('alternative_allele_count', 'A'), explanation: 'Сумират се локалните алелни дозировки.' })
  } else if (type === 'COHORT_MEAN_AGE') {
    rows.push({ title: 'Глобален брой пациенти', formula: sumFormula('cohort_size', 'N'), explanation: 'Сума на локалните целеви групи.' })
    rows.push({ title: 'Глобална сума на възрастите', formula: sumFormula('age_sum', 'S'), explanation: 'Индивидуалните възрасти не се разкриват.' })
  } else if (type === 'THERAPY_RESPONSE_RATE') {
    rows.push({ title: 'Глобален брой лекувани', formula: sumFormula('cohort_size', 'N'), explanation: 'Сума на лекуваните пациенти.' })
    rows.push({ title: 'Глобален брой отговорили', formula: sumFormula('responder_count', 'R'), explanation: 'Сума на пациентите с RESPONDER.' })
  } else {
    for (const [key, symbol] of [['a', 'A'], ['b', 'B'], ['c', 'C'], ['d', 'D']])
      rows.push({ title: `Глобална клетка ${symbol}`, formula: sumFormula(key, symbol), explanation: 'Сумиране на съответната клетка от всички участващи болници.' })
    const r = verification.value.reference
    rows.push({ title: 'Защитено произведение AD', formula: `AD = ${r.a} × ${r.d} = ${r.ad}`, explanation: 'Умножение с помощта на BGW, последвано от редукция на степента.' })
    rows.push({ title: 'Защитено произведение BC', formula: `BC = ${r.b} × ${r.c} = ${r.bc}`, explanation: 'Умножение с помощта на BGW, последвано от редукция на степента.' })
  }
  rows.push({ title: 'Крайно изчисление след реконструкция', formula: demoEquation.value, explanation: 'Формулата използва само разрешените глобални стойности.' })
  return rows
})
const activeSession = computed(() => sessions.value[sessions.value.length - 1])
const participantLabels = computed(() => study.value?.participants.map(p => `P${p.participant_index}`).join(', ') || '')
function auditActorLabel(event: Audit): string {
  if (event.actor_role === 'ORG_ADMIN') return event.organization_name || event.actor_name || 'Администратор на организация'
  if (event.actor_role === 'RESEARCHER') return `${event.actor_name || 'Изследовател'} · Изследовател`
  if (event.actor_role === 'SYSTEM_ADMIN') return `${event.actor_name || 'Системен администратор'} · Системен администратор`
  return 'Системно действие'
}
const traceLabels: Record<string, string> = {
  shamir_share: 'Генериране и разпределяне на Shamir дялове',
  receive_input_share: 'Получаване на входен дял', add: 'Локално събиране на дялове',
  multiply_constant: 'Локално умножение с константа',
  local_product_and_reshare: 'Локално произведение и повторно споделяне',
  receive_degree_reduction_reshare: 'Получаване на дял за редукция',
  lagrange_combine_reshares: 'Редукция на степента чрез интерполация на Лагранж - коефициенти'
}
const phaseLabels: Record<string, string> = {
  input_sharing: 'Споделяне на локален вход', share_distribution: 'Обмен на дялове',
  secure_computation: 'Сигурно изчисление', multiplication: 'Сигурно умножение',
  degree_reduction: 'Редукция на степента'
}
function wireLabel(value: unknown): string {
  const name = String(value ?? '')
  if (name.startsWith('cohort_count_') || name === 'cohort_total' || name === 'therapy_cohort_total') return 'брой пациенти в целевата група'
  if (name.startsWith('variant_count_') || name === 'variant_total') return 'брой носители на варианта'
  if (name.startsWith('metric_')) return 'локална стойност на анализираната метрика'
  if (name.startsWith('denominator_')) return 'локален брой пациенти'
  if (name === 'alternative_allele_total') return 'общ брой алтернативни алела'
  if (name === 'age_sum_total') return 'обща сума на възрастите'
  if (name === 'responder_total') return 'общ брой отговорили пациенти'
  if (name === 'treated_total') return 'общ брой лекувани пациенти'
  if (/^[abcd]_p\d+$/.test(name)) return 'локална клетка от таблицата за асоциация'
  if (['A', 'B', 'C', 'D'].includes(name)) return 'глобална клетка от таблицата за асоциация'
  if (['AD', 'BC'].includes(name)) return 'дял от произведението'
  if (name.startsWith('__sum_') || name.startsWith('__therapy_')) return 'междинна сума'
  return 'поверителна стойност'
}
function eventShares(event: Record<string, unknown>, key: 'shares' | 'reshares') {
  return (Array.isArray(event[key]) ? event[key] : []) as Array<{ recipient: number; x?: number; value: string }>
}
function reductionRows(event: Record<string, unknown>) {
  const coefficients = (event.lagrange_coefficients || {}) as Record<string, string>
  const received = (event.received_reshares || {}) as Record<string, string>
  return Object.keys(coefficients).map(source => ({ source, coefficient: coefficients[source], share: received[source] }))
}
function operationFormula(event: Record<string, unknown>): string {
  const operation = String(event.operation)
  if (operation === 'add') return `(${event.left_share} + ${event.right_share}) mod p = ${event.result_share}`
  if (operation === 'multiply_constant') return `Умножение с публична константа ${event.constant} → нов дял = ${event.result_share}`
  if (operation === 'local_product_and_reshare') return `(${event.left_share} × ${event.right_share}) mod p = ${event.degree_2_share}`
  if (operation === 'lagrange_combine_reshares') return `Σ λⱼ × dⱼ mod p = ${event.result_share}`
  return ''
}
function operationExplanation(event: Record<string, unknown>, participant: number): string {
  const operation = String(event.operation)
  if (operation === 'add') return `P${participant} държи дялове на локалните стойности от различните болници. Той ги събира, защото споделянето на дялове е линейно: сборът на дяловете е валиден дял от сбора на тайните стойности. Така постепенно се получава дял за ${wireLabel(event.out)}, без P${participant} да научава нито една локална стойност.`
  if (operation === 'multiply_constant') return `P${participant} умножава своя дял по публична константа. Това е локална операция и не изисква разкриване или обмен на допълнителни данни. Получава се валиден дял за ${wireLabel(event.out)}.`
  if (operation === 'local_product_and_reshare') return `P${participant} умножава своите дялове на двете глобални клетки, защото за odds ratio са необходими кръстосаните произведения. Умножението повишава степента на полинома от 1 на 2. Затова полученият дял не може да се използва директно и се споделя повторно между P1, P2 и P3.`
  if (operation === 'lagrange_combine_reshares') return `P${participant} е получил по един повторно споделен дял от всеки участник. След това с интерполация на Лагранж се премахва допълнителната степен от умножението и се създава нов дял от степен 1, който отново отговаря на първоначалния праг t = 1.`
  return ''
}

function studyModeBadgeClass(mode: Study['study_mode']): string {
  if (mode === 'DEMONSTRATION') return 'bg-amber-100 text-amber-800'
  return 'bg-pine-50 text-pine-700'
}

function studyModeLabel(mode: Study['study_mode']): string {
  if (mode === 'DEMONSTRATION') return 'Демонстрационен режим'
  return 'Сигурен режим'
}

function tabButtonClass(tab: StudyTab): string {
  if (activeTab.value === tab) return 'bg-pine-700 text-white shadow-sm'
  return 'text-mist hover:bg-paper hover:text-ink'
}

function sexLabel(sex: string | null): string {
  if (sex === 'F') return 'Жени'
  if (sex === 'M') return 'Мъже'
  return 'Всички'
}

function protocolPhaseClass(index: number): string {
  if (study.value?.status === 'COMPLETED') return 'bg-pine-600 text-white'
  if (study.value?.status === 'COMPUTING' && index === 3) {
    return 'bg-pine-600 text-white ring-4 ring-pine-100'
  }
  return 'bg-paper text-mist'
}

function protocolPhaseMarker(index: number): string | number {
  if (study.value?.status === 'COMPLETED') return '✓'
  return index + 1
}

function verificationActionLabel(): string {
  if (verification.value) return 'Провери отново'
  return 'Стартирай проверката'
}

function verificationStatusClass(): string {
  if (verification.value?.verified) return 'border-pine-300 bg-pine-100 text-pine-800'
  return 'border-red-200 bg-red-50 text-brick'
}

function verificationStatusLabel(): string {
  if (verification.value?.verified) return 'Проверката е успешна — резултатите съвпадат'
  return 'Резултатите не съвпадат'
}

function verificationPrompt(): string {
  if (a.user?.role === 'ORG_ADMIN') return 'Проверката може да бъде стартирана от изследователя.'
  return 'Стартирайте независимото референтно изчисление.'
}

async function approval(approve: boolean) {
  busy.value = true
  try {
    study.value = (await api.post(`/studies/${route.params.id}/approval`, { approve })).data
    toast.success(approve ? 'Участието е одобрено.' : 'Поканата е отхвърлена.')
    await load()
  } catch (e) {
    toast.error(errorText(e))
  } finally {
    busy.value = false
  }
}

async function run() {
  busy.value = true
  try {
    await api.post(`/studies/${route.params.id}/run`)
    toast.info('Сигурното изчисление е стартирано.')
    await load()
  } catch (e) {
    toast.error(errorText(e))
  } finally {
    busy.value = false
  }
}

async function verifyResult() {
  verifying.value = true
  try {
    verification.value = (await api.post(`/studies/${route.params.id}/verify`)).data
    toast.success('Проверката е завършена.')
  } catch (e) { toast.error(errorText(e)) }
  finally { verifying.value = false }
}
</script>

<template>
  <div v-if="study">
    <PageHead :eyebrow="tr(study.analysis_type)" :title="study.name" :description="study.description || 'Защитено многоцентрово медицинско проучване'">
      <span
        class="rounded-full px-3 py-1.5 text-xs font-semibold"
        :class="studyModeBadgeClass(study.study_mode)"
      >{{ studyModeLabel(study.study_mode) }}</span>
      <StatusBadge :value="study.status" />
      <button v-if="canRun && a.user?.role !== 'ORG_ADMIN'" class="btn-primary !gap-1.5 !px-3 !py-2 !text-xs" :disabled="busy" @click="run">
        <Spinner v-if="busy" :size="16" />
        <Play v-else :size="16" />
        Стартирай MPC
      </button>
    </PageHead>

    <section
      v-if="a.user?.role === 'ORG_ADMIN' && myParticipant?.status === 'INVITED'"
      class="mb-4 flex flex-wrap items-center gap-3 rounded-xl border-l-4 border-amber-500 bg-white p-5 ring-1 ring-line"
    >
      <div class="grow leading-snug">
        <b class="text-[13px]">Вашата организация е поканена</b>
        <p class="mt-0.5 text-xs text-mist">Прегледайте детайлите на изследването и вземете решение дали ще участвате в него.</p>
      </div>
      <button class="btn-danger !gap-1.5 !px-3 !py-2 !text-xs" :disabled="busy" @click="approval(false)"><X :size="16" />Отхвърли</button>
      <button class="btn-primary !gap-1.5 !px-3 !py-2 !text-xs" :disabled="busy" @click="approval(true)"><Check :size="16" />Одобри</button>
    </section>

    <nav class="panel mb-4 flex gap-1 overflow-x-auto p-1.5" aria-label="Раздели на проучването">
      <button v-for="tab in studyTabs" :key="tab.value" type="button"
        class="shrink-0 rounded-lg px-4 py-2.5 text-xs font-semibold transition"
        :class="tabButtonClass(tab.value)"
        @click="activeTab = tab.value">{{ tab.label }}</button>
    </nav>

    <div v-show="activeTab === 'overview' || activeTab === 'participants'" class="mb-4 grid gap-4 lg:grid-cols-1">
      <section v-show="activeTab === 'overview'" class="panel p-6">
        <h2 class="mb-4 text-base font-bold">Критерии за целевата група</h2>
        <dl class="grid grid-cols-2 gap-x-4 gap-y-4">
          <div><dt class="text-xs text-mist">Заболяване</dt><dd class="mt-0.5 text-[13px] font-semibold">{{ study.criteria.disease_code || 'Всички' }}</dd></div>
          <div><dt class="text-xs text-mist">Генетичен вариант</dt><dd class="mt-0.5 text-[13px] font-semibold">{{ study.criteria.variant_code }}</dd></div>
          <div><dt class="text-xs text-mist">Терапия</dt><dd class="mt-0.5 text-[13px] font-semibold">{{ study.criteria.therapy_code || 'Не е приложимо' }}</dd></div>
          <div><dt class="text-xs text-mist">Възраст</dt><dd class="mt-0.5 text-[13px] font-semibold">{{ study.criteria.min_age ?? 'Без минимум' }}–{{ study.criteria.max_age ?? 'Без максимум' }}</dd></div>
          <div><dt class="text-xs text-mist">Пол</dt><dd class="mt-0.5 text-[13px] font-semibold">{{ sexLabel(study.criteria.sex) }}</dd></div>
        </dl>
      </section>

      <section v-show="activeTab === 'participants'" class="panel p-6">
        <h2 class="mb-2 text-base font-bold">Одобрения от болниците</h2>
        <div
          v-for="p in study.participants" :key="p.organization_id"
          class="flex items-center gap-3 border-t border-line/70 py-2.5 first:border-t-0"
        >
          <span class="grid size-8 shrink-0 place-items-center rounded-lg bg-pine-50 text-[11px] font-bold text-pine-700">P{{ p.participant_index }}</span>
          <div class="min-w-0 grow leading-snug">
            <b class="block truncate text-xs">{{ p.organization_name }}</b>
            <small class="text-xs text-mist">Участник {{ p.participant_index }}</small>
            <small v-if="a.user?.role !== 'ORG_ADMIN' && ['APPROVED','COMPLETED'].includes(p.status)" class="block text-[11px] text-pine-600">Локална обработка на данните е завършена. Стойностите остават поверителни.</small>
          </div>
          <StatusBadge :value="p.status" />
        </div>
      </section>
    </div>

    <section v-show="activeTab === 'participants'" v-if="a.user?.role === 'ORG_ADMIN' && localInput" class="panel mb-4 overflow-hidden">
      <header class="flex items-start justify-between gap-4 border-b border-line px-6 py-5">
        <div><span class="text-xs font-semibold text-pine-600">{{ localInput.organization }}</span><h2 class="mt-1 text-lg font-bold">Локален вход за проучването</h2></div>
        <span class="rounded-full bg-pine-50 px-3 py-1.5 text-xs font-semibold text-pine-700">Поверително</span>
      </header>
      <div v-if="study.analysis_type === 'VARIANT_FREQUENCY'" class="grid gap-4 p-6 sm:grid-cols-2">
        <div class="rounded-2xl bg-paper p-5"><span class="text-xs text-mist">Съвпадащи пациенти</span><b class="mt-2 block text-3xl">{{ localInput.cohort_size }}</b></div>
        <div class="rounded-2xl bg-pine-50 p-5"><span class="text-xs text-pine-700">Носители на варианта</span><b class="mt-2 block text-3xl text-pine-800">{{ localInput.variant_count }}</b></div>
      </div>
      <div v-else-if="study.analysis_type === 'ALLELE_FREQUENCY'" class="grid gap-4 p-6 sm:grid-cols-2">
        <div class="rounded-2xl bg-paper p-5"><span class="text-xs text-mist">Съвпадащи пациенти</span><b class="mt-2 block text-3xl">{{ localInput.cohort_size }}</b></div>
        <div class="rounded-2xl bg-pine-50 p-5"><span class="text-xs text-pine-700">Алтернативни алели</span><b class="mt-2 block text-3xl">{{ localInput.alternative_allele_count }}</b></div>
      </div>
      <div v-else-if="study.analysis_type === 'COHORT_MEAN_AGE'" class="grid gap-4 p-6 sm:grid-cols-3">
        <div class="rounded-2xl bg-paper p-5"><span class="text-xs text-mist">Пациенти</span><b class="mt-2 block text-3xl">{{ localInput.cohort_size }}</b></div>
        <div class="rounded-2xl bg-paper p-5"><span class="text-xs text-mist">Сума на възрастите</span><b class="mt-2 block text-3xl">{{ localInput.age_sum }}</b></div>
        <div class="rounded-2xl bg-pine-50 p-5"><span class="text-xs text-pine-700">Локална средна възраст</span><b class="mt-2 block text-3xl">{{ localInput.local_mean_age }}</b></div>
      </div>
      <div v-else-if="study.analysis_type === 'THERAPY_RESPONSE_RATE'" class="grid gap-4 p-6 sm:grid-cols-2">
        <div class="rounded-2xl bg-paper p-5"><span class="text-xs text-mist">Лекувани пациенти</span><b class="mt-2 block text-3xl">{{ localInput.treated_count }}</b></div>
        <div class="rounded-2xl bg-pine-50 p-5"><span class="text-xs text-pine-700">Отговорили</span><b class="mt-2 block text-3xl">{{ localInput.responder_count }}</b></div>
      </div>
      <div v-else class="grid gap-3 p-6 sm:grid-cols-2 lg:grid-cols-4">
        <div v-for="item in [{k:'A',v:localInput.a,l:'Вариант + отговор'}, {k:'B',v:localInput.b,l:'Вариант + без отговор'}, {k:'C',v:localInput.c,l:'Без вариант + отговор'}, {k:'D',v:localInput.d,l:'Без вариант + без отговор'}]" :key="item.k" class="rounded-2xl bg-paper p-4">
          <span class="text-xs text-mist">{{ item.k }} · {{ item.l }}</span><b class="mt-2 block text-2xl">{{ item.v }}</b>
        </div>
      </div>
      <footer class="grid gap-2 border-t border-line bg-pine-900 px-6 py-4 text-xs text-pine-200 sm:grid-cols-3">
        <span>Локалните данни са изчислени</span><span>Споделят се само Shamir дялове</span><span>Кординаторът не получава тези стойности</span>
      </footer>
    </section>

    <section v-if="false" class="panel mb-4 p-6">
      <h2 class="mb-6 text-base font-bold">Изпълнение на протокола</h2>
      <div class="grid grid-cols-[repeat(5,minmax(110px,1fr))] overflow-x-auto">
        <div
          v-for="(x, i) in phases" :key="x"
          class="relative text-center before:absolute before:inset-x-0 before:top-3.5 before:h-0.5 before:bg-line first:before:left-1/2 last:before:right-1/2"
        >
          <i
            class="relative z-10 mx-auto grid size-7 place-items-center rounded-full text-[11px] not-italic"
            :class="protocolPhaseClass(i)"
          >{{ protocolPhaseMarker(i) }}</i>
          <span class="mt-2 block px-1 text-[11px] leading-tight text-mist">{{ x }}</span>
        </div>
      </div>
    </section>
    <section v-if="false" class="panel mb-4 p-6">
      <h2 class="text-base font-bold">Изчисление</h2><p class="mt-2 text-sm text-mist">MPC сесията ще се появи тук, след като всички организации одобрят участието и изчислението бъде стартирано.</p>
    </section>

    <section v-show="activeTab === 'overview'" v-if="study.result" class="mb-4 flex gap-4 rounded-xl bg-pine-900 p-6 text-white">
      <ShieldCheck class="shrink-0 text-pine-300" :size="22" />
      <div>
        <span class="text-xs text-pine-300">Краен резултат от изпълнението на протокола</span>
        <h2 v-if="study.result.suppressed" class="mt-1 text-2xl font-bold tracking-tight">Резултатът е поверителен</h2>
        <template v-else-if="study.analysis_type === 'VARIANT_FREQUENCY'">
          <h2 class="mt-1 text-2xl font-bold tabular-nums tracking-tight">{{ Number(study.result.frequency_percent).toFixed(2) }}%</h2>
          <p class="mt-1 text-xs text-pine-200">{{ study.result.variant_count }} носители на варианта в обща целева група от {{ study.result.cohort_size }}.</p>
        </template>
        <template v-else-if="['ALLELE_FREQUENCY','COHORT_MEAN_AGE','THERAPY_RESPONSE_RATE'].includes(study.analysis_type)">
          <h2 class="mt-1 text-2xl font-bold tabular-nums tracking-tight">{{ resultHeadline }}</h2>
          <p class="mt-1 text-xs text-pine-200">{{ resultDetails }}</p>
        </template>
        <template v-else>
          <h2 class="mt-1 text-2xl font-bold tabular-nums tracking-tight">{{ Number(study.result.odds_ratio).toFixed(2) }} отношение на шансовете</h2>
          <p class="mt-1 text-xs text-pine-200">Общ размер на целевата група: {{ study.result.cohort_size }} пациенти.</p>
        </template>
      </div>
    </section>

    <section v-if="activeTab === 'overview' && resultInterpretation" class="panel mb-4 overflow-hidden">
      <header class="flex items-center gap-3 border-b border-line px-6 py-5">
        <span class="grid size-9 shrink-0 place-items-center rounded-xl bg-pine-50 text-pine-700"><Lightbulb :size="18" /></span>
        <div><span class="text-xs font-semibold text-pine-600">Значение на получения резултат</span><h2 class="mt-0.5 text-base font-bold">Интерпретация и извод</h2></div>
      </header>
      <div class="grid gap-4 p-6 md:grid-cols-2">
        <article class="rounded-xl border border-line bg-paper/50 p-4">
          <h3 class="text-sm font-bold">Интерпретация</h3>
          <p class="mt-2 text-sm leading-6 text-ink/80">{{ resultInterpretation.interpretation }}</p>
        </article>
        <article class="rounded-xl border border-line bg-paper/50 p-4">
          <h3 class="text-sm font-bold">Извод</h3>
          <p class="mt-2 text-sm leading-6 text-ink/80">{{ resultInterpretation.conclusion }}</p>
        </article>
        <p class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900 md:col-span-2"><b>Важно:</b> Изводът от проучването е интерпретация на резултата. Той не представлява диагноза, доказателство за причината на заболяване или самостоятелна препоръка за лечение.</p>
      </div>
    </section>

    <section v-if="activeTab === 'overview' && (study.status === 'COMPUTING' || sessions.length)" class="panel mb-4 p-6">
      <h2 class="mb-6 text-base font-bold">Изпълнение на протокола</h2>
      <div class="grid grid-cols-[repeat(5,minmax(110px,1fr))] overflow-x-auto">
        <div v-for="(phase, index) in phases" :key="phase"
          class="relative text-center before:absolute before:inset-x-0 before:top-3.5 before:h-0.5 before:bg-line first:before:left-1/2 last:before:right-1/2">
          <i class="relative z-10 mx-auto grid size-7 place-items-center rounded-full text-[11px] not-italic"
            :class="protocolPhaseClass(index)">{{ protocolPhaseMarker(index) }}</i>
          <span class="mt-2 block px-1 text-[11px] leading-tight text-mist">{{ phase }}</span>
        </div>
      </div>
    </section>

    <section v-show="activeTab === 'verification'" v-if="study.status === 'COMPLETED'" class="panel mb-4 overflow-hidden">
      <header class="flex flex-wrap items-center justify-between gap-4 border-b border-line px-6 py-5">
        <div><span class="text-xs font-semibold text-amber-700">Проверка на коректността</span><h2 class="mt-1 text-lg font-bold">Сравнителен анализ на резултатите, получени с и без прилагане на протокола</h2></div>
        <button v-if="study.study_mode === 'DEMONSTRATION' && a.user?.role !== 'ORG_ADMIN'" class="btn-primary !gap-1.5 !px-3 !py-2 !text-xs" :disabled="verifying" @click="verifyResult">
          <Spinner v-if="verifying" :size="16" />{{ verificationActionLabel() }}
        </button>
      </header>
      <div v-if="study.study_mode === 'SECURE'" class="p-6">
        <b class="text-sm">Проверката не е налична</b>
        <p class="mt-1 text-xs text-mist">Проверката не е налична в режим за сигурни проучвания.</p>
      </div>
      <div v-else class="p-6 text-xs">
        <div class="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">
          <b>Демонстрационен режим</b>
          <p class="mt-1">Явните стойности се използват единствено за проверка на коректността на резултата от протокола.</p>
        </div>
        <div class="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <article
            v-for="step in verificationOverviewSteps" :key="step.number"
            class="rounded-xl border p-4 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md"
            :class="step.cardClass"
          >
            <span class="grid size-7 place-items-center rounded-full text-xs font-bold shadow-sm" :class="step.badgeClass">{{ step.number }}</span>
            <b class="mt-3 block text-sm" :class="step.titleClass">{{ step.title }}</b>
            <p class="mt-1 text-xs leading-relaxed text-mist">{{ step.description }}</p>
          </article>
        </div>
        <section class="mb-6 rounded-xl border border-pine-200 bg-pine-50/40 p-5">
          <h3 class="text-sm font-bold text-pine-900">Схема на протокола и използвани формули</h3>
          <dl v-if="activeSession" class="mt-4 grid gap-3 rounded-lg border border-pine-100 bg-white/80 p-4 text-xs sm:grid-cols-3">
            <div><dt class="text-mist">Крайно поле GF(p)</dt><dd class="mt-1 break-all font-mono font-semibold">p = {{ activeSession.field_prime }}</dd></div>
            <div><dt class="text-mist">Праг</dt><dd class="mt-1 font-mono font-semibold">t = {{ activeSession.threshold }}</dd></div>
            <div><dt class="text-mist">Участници</dt><dd class="mt-1 font-mono font-semibold">{{ participantLabels }}</dd></div>
          </dl>
          <ol class="mt-4 grid gap-3">
            <li v-for="(line, index) in demoCircuit" :key="line" class="flex items-start gap-3 text-xs">
              <span class="grid size-6 shrink-0 place-items-center rounded-lg border border-pine-300 bg-white font-bold text-pine-800">{{ index + 1 }}</span>
              <code class="rounded-md border border-line bg-white px-3 py-2 font-mono font-semibold text-pine-900">{{ line }}</code>
            </li>
          </ol>
          <p class="mt-4 rounded-lg bg-pine-900 px-4 py-3 text-xs text-pine-100"><b>Важно:</b> реалните стойности на дяловете не се реконструират и не се показват. Демонстрацията разкрива локалните данни единствено за доказване на коректността на изпълнение на протокола.</p>
        </section>
        <div v-if="verification" class="space-y-5">
          <section class="rounded-xl border border-pine-100 bg-pine-50/35 p-5">
            <h3 class="mb-3 flex items-center gap-2 text-sm font-bold text-pine-800">
              <span class="grid size-6 shrink-0 place-items-center rounded-full bg-pine-300 text-xs text-pine-900">1</span>
              Локални входни данни
            </h3>
            <div class="overflow-x-auto rounded-xl border border-pine-100 bg-white">
              <table class="table-base !text-xs">
                <thead><tr><th>Болница</th><th v-for="metric in demoMetrics" :key="metric.key">{{ metric.label }}</th></tr></thead>
                <tbody><tr v-for="input in verification.local_breakdown" :key="String(input.organization)"><td class="font-semibold">{{ input.organization }}</td><td v-for="metric in demoMetrics" :key="metric.key" class="font-mono">{{ input[metric.key] }}</td></tr></tbody>
              </table>
            </div>
          </section>
          <section class="rounded-xl border border-pine-200 bg-pine-50/60 p-5">
            <h3 class="mb-3 flex items-center gap-2 text-sm font-bold text-pine-800">
              <span class="grid size-6 shrink-0 place-items-center rounded-full bg-pine-400 text-xs text-white">2</span>
              Извършени изчисления
            </h3>
            <div class="grid gap-3">
              <article v-for="(entry, index) in numericTrace" :key="entry.title" class="rounded-xl border border-pine-100 bg-white/85 p-4">
                <div class="flex items-start gap-3"><span class="grid size-7 shrink-0 place-items-center rounded-full border border-pine-300 bg-pine-50 text-xs font-bold text-pine-800">{{ index + 1 }}</span>
                  <div class="min-w-0"><b class="text-sm">{{ entry.title }}</b><p class="mt-1 text-xs text-mist">{{ entry.explanation }}</p>
                    <code class="mt-3 block overflow-x-auto rounded-lg border border-pine-100 bg-pine-50/40 px-4 py-3 font-mono text-xs font-bold text-pine-900">{{ entry.formula }}</code>
                  </div>
                </div>
              </article>
            </div>
          </section>
          <section class="rounded-xl border border-pine-300 bg-pine-100/45 p-5">
            <h3 class="mb-1 flex items-center gap-2 text-sm font-bold text-pine-900">
              <span class="grid size-6 shrink-0 place-items-center rounded-full bg-pine-500 text-xs text-white">3</span>
              Детайли от изпълнението на протокола
            </h3>
            <p class="mb-4 text-xs leading-relaxed text-mist">Това са събитията, записани по време на изпълнението на BGW. Стойностите са елементи на крайното поле GF(p) и са показани, понеже проучването е в демонстрационен режим.</p>
            <div class="mb-5 grid gap-3 md:grid-cols-3">
              <article class="rounded-xl border border-pine-200 bg-white/85 p-4"><b class="text-sm text-pine-900">1. Всяка болница разделя входните си данни</b><p class="mt-2 text-xs leading-relaxed text-mist">Локалната стойност се представя чрез три дяла. P1, P2 и P3 получават по един дял. Един отделен дял не е достатъчен за възстановяване на стойността.</p></article>
              <article class="rounded-xl border border-pine-200 bg-white/85 p-4"><b class="text-sm text-pine-900">2. Всеки участник събира своите дялове</b><p class="mt-2 text-xs leading-relaxed text-mist">Например P1 събира дяла, получен от болница 1, с дяловете от болници 2 и 3.</p></article>
              <article class="rounded-xl border border-pine-200 bg-white/85 p-4"><b class="text-sm text-pine-900">3. Реконструира се само крайния резултат</b><p class="mt-2 text-xs leading-relaxed text-mist">Накрая дяловете се реконструират чрез интерполация. Локалните и междинни стойности в изчислението не подлежат на реконструкция.</p></article>
            </div>
            <div class="mb-5 rounded-xl border border-pine-300 bg-white/70 p-5">
              <h4 class="text-sm font-bold text-pine-900">Защо сборът на дяловете представлява сбор на тайните?</h4>
              <p class="mt-2 text-xs leading-relaxed text-mist">Ако болница 1 сподели тайна стойност чрез полином f₁(x), болница 2 чрез f₂(x), а болница 3 чрез f₃(x), всеки участник събира стойностите при собствената си координата x. Получава се:</p>
              <code class="mt-3 block overflow-x-auto rounded-lg border border-pine-200 bg-pine-50/60 px-4 py-3 font-mono text-xs font-bold text-pine-900">f₁(x) + f₂(x) + f₃(x) = fобщо(x)</code>
              <p class="mt-2 text-xs leading-relaxed text-mist">Свободният член на новия полином е сборът на тайните стойности от всички участващи болници. Следователно участниците вече държат дялове на общия резултат, без някой да е виждал отделните входове.</p>
            </div>
            <div v-if="verification.protocol_trace?.length" class="grid gap-4">
              <details v-for="node in verification.protocol_trace" :key="node.participant_id" class="overflow-hidden rounded-xl border border-pine-300 bg-white/70" open>
                <summary class="cursor-pointer bg-pine-200/70 px-5 py-4 text-sm font-bold text-pine-900">Болница P{{ node.participant_id }} · {{ node.events.length }} събития</summary>
                <div class="grid gap-3 border-t border-line p-4">
                  <article v-for="(event, index) in node.events" :key="index" class="rounded-lg border border-pine-200 bg-white/80 p-4 text-xs">
                    <div class="flex flex-wrap items-center justify-between gap-2"><b>{{ index + 1 }}. {{ traceLabels[String(event.operation)] || 'Протоколна операция' }}</b><span class="rounded bg-paper px-2 py-1 text-[10px] text-mist">{{ phaseLabels[String(event.phase)] || 'BGW обработка' }}</span></div>
                    <template v-if="event.operation === 'shamir_share'">
                      <p class="mt-3 text-mist">Болницата е изчислила <b class="text-ink">{{ wireLabel(event.value_name) }}</b> със стойност <b class="text-ink">{{ event.secret }}</b>. Тя не изпраща тази стойност директно. Вместо това я разделя на три тайни дяла чрез случаен полином от първа степен, за да може всеки участник да работи само със своя дял.</p>
                      <div class="mt-3 overflow-x-auto rounded-lg border border-line"><table class="table-base !text-xs"><thead><tr><th>Получател</th><th>Координата x</th><th>Стойност на дял в GF(p)</th></tr></thead><tbody><tr v-for="share in eventShares(event, 'shares')" :key="share.recipient"><td>P{{ share.recipient }}</td><td>{{ share.x }}</td><td class="font-mono">{{ share.value }}</td></tr></tbody></table></div>
                    </template>
                    <template v-else-if="event.operation === 'receive_input_share'">
                      <p class="mt-3 text-mist">P{{ node.participant_id }} получава от P{{ event.sender }} тайния дял за <b class="text-ink">{{ wireLabel(event.value_name) }}</b>. Този дял ще бъде събран с дяловете от останалите болници. Самостоятелно той не разкрива локалната стойност на изпращащия.</p>
                      <code class="mt-2 block overflow-x-auto rounded-lg bg-paper px-3 py-2 font-mono">дял = {{ event.share }}</code>
                    </template>
                    <template v-else-if="event.operation === 'add' || event.operation === 'multiply_constant'">
                      <p class="mt-3 text-mist">{{ operationExplanation(event, node.participant_id) }}</p>
                      <code class="mt-2 block overflow-x-auto rounded-lg border border-line bg-white px-3 py-2 font-mono font-bold text-pine-900">{{ operationFormula(event) }}</code>
                    </template>
                    <template v-else-if="event.operation === 'local_product_and_reshare'">
                      <p class="mt-3 text-mist">{{ operationExplanation(event, node.participant_id) }}</p>
                      <code class="mt-2 block overflow-x-auto rounded-lg border border-line bg-white px-3 py-2 font-mono font-bold text-pine-900">{{ operationFormula(event) }}</code>
                      <div class="mt-3 overflow-x-auto rounded-lg border border-line"><table class="table-base !text-xs"><thead><tr><th>Получател</th><th>Повторно споделен дял</th></tr></thead><tbody><tr v-for="share in eventShares(event, 'reshares')" :key="share.recipient"><td>P{{ share.recipient }}</td><td class="font-mono">{{ share.value }}</td></tr></tbody></table></div>
                    </template>
                    <template v-else-if="event.operation === 'receive_degree_reduction_reshare'">
                      <p class="mt-3 text-mist">P{{ node.participant_id }} получава от P{{ event.sender }} повторно споделен дял от произведението. Той не се събира като обикновена сума, а ще бъде комбиниран с Лагранжов коефициент. Трите дяла са необходими за премахване на допълнителната степен, възникнала при умножението.</p>
                      <code class="mt-2 block overflow-x-auto rounded-lg bg-paper px-3 py-2 font-mono">получен дял = {{ event.share }}</code>
                    </template>
                    <template v-else-if="event.operation === 'lagrange_combine_reshares'">
                      <p class="mt-3 text-mist">{{ operationExplanation(event, node.participant_id) }}</p>
                      <div class="mt-3 overflow-x-auto rounded-lg border border-line"><table class="table-base !text-xs"><thead><tr><th>Източник</th><th>Лагранжов коефициент λ</th><th>Получен дял</th></tr></thead><tbody><tr v-for="row in reductionRows(event)" :key="row.source"><td>P{{ row.source }}</td><td class="font-mono">{{ row.coefficient }}</td><td class="font-mono">{{ row.share }}</td></tr></tbody></table></div>
                      <code class="mt-3 block overflow-x-auto rounded-lg border border-line bg-white px-3 py-2 font-mono font-bold text-pine-900">{{ operationFormula(event) }}</code>
                    </template>
                    <p v-else class="mt-3 text-mist">Болница изпълнява необходима стъпка от протокола, без да реконструира поверителните входни данни.</p>
                  </article>
                </div>
              </details>
            </div>
            <div v-else class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">За тази по-стара демонстрационна сесия няма записани данни. Стартирайте ново демонстрационно проучване, за да се запишат действителните Shamir дялове и стъпки за редукция на степента на полинома.</div>
          </section>
          <section class="rounded-xl border border-pine-300 bg-pine-100/60 p-5">
            <h3 class="flex items-center gap-2 text-sm font-bold text-pine-900">
              <span class="grid size-6 shrink-0 place-items-center rounded-full bg-pine-600 text-xs text-white">4</span>
              Референтно изчисление с явни стойности
            </h3>
            <p class="mt-2 text-xs leading-relaxed text-mist">Локалните данни от таблицата се сумират директно, без използването на MPC.</p>
            <code class="mt-3 block overflow-x-auto rounded-lg border border-pine-200 bg-white/85 px-4 py-3 font-mono text-xs font-bold text-pine-900">{{ demoEquation }}</code>
          </section>
          <section class="rounded-xl border border-pine-400 bg-pine-200/35 p-5">
            <h3 class="flex items-center gap-2 text-sm font-bold text-pine-900">
              <span class="grid size-6 shrink-0 place-items-center rounded-full bg-pine-700 text-xs text-white">5</span>
              Сравнение на резултатите
            </h3>
            <p class="mt-2 text-xs leading-relaxed text-mist">За всеки краен резултат се изчислява абсолютна разлика |Явен резултат − BGW|. Проверката е успешна, когато всички разлики са най-много {{ verification.tolerance }}.</p>
            <div class="mt-4 overflow-x-auto rounded-xl border border-pine-300 bg-white">
              <table class="table-base !text-xs">
                <thead><tr><th>Метрика</th><th>Явен резултат</th><th>BGW</th><th>Разлика</th></tr></thead>
                <tbody v-if="study.analysis_type === 'VARIANT_FREQUENCY'">
                  <tr><td>Обща целева група</td><td>{{ verification.reference.cohort_size }}</td><td>{{ verification.bgw.cohort_size }}</td><td>{{ verification.differences.cohort_size }}</td></tr>
                  <tr><td>Носители</td><td>{{ verification.reference.variant_count }}</td><td>{{ verification.bgw.variant_count }}</td><td>{{ verification.differences.variant_count }}</td></tr>
                  <tr><td>Честота</td><td>{{ verification.reference.frequency_percent }}%</td><td>{{ verification.bgw.frequency_percent }}%</td><td>{{ verification.differences.frequency_percent }}</td></tr>
                </tbody>
                <tbody v-else-if="study.analysis_type === 'ALLELE_FREQUENCY'">
                  <tr><td>Алелна честота</td><td>{{ verification.reference.allele_frequency_percent }}%</td><td>{{ verification.bgw.allele_frequency_percent }}%</td><td>{{ verification.differences.allele_frequency_percent }}</td></tr>
                </tbody>
                <tbody v-else-if="study.analysis_type === 'COHORT_MEAN_AGE'">
                  <tr><td>Средна възраст</td><td>{{ verification.reference.mean_age }}</td><td>{{ verification.bgw.mean_age }}</td><td>{{ verification.differences.mean_age }}</td></tr>
                </tbody>
                <tbody v-else-if="study.analysis_type === 'THERAPY_RESPONSE_RATE'">
                  <tr><td>Честота на отговор</td><td>{{ verification.reference.response_rate_percent }}%</td><td>{{ verification.bgw.response_rate_percent }}%</td><td>{{ verification.differences.response_rate_percent }}</td></tr>
                </tbody>
                <tbody v-else><tr><td>Odds ratio</td><td>{{ verification.reference.odds_ratio }}</td><td>{{ verification.bgw.odds_ratio }}</td><td>{{ verification.differences.odds_ratio }}</td></tr></tbody>
              </table>
            </div>
            <div class="mt-4 rounded-xl border p-4 text-xs font-bold" :class="verificationStatusClass()">
              {{ verificationStatusLabel() }}
            </div>
          </section>
          <details class="rounded-xl border border-pine-300 bg-pine-100/40 p-4">
            <summary class="cursor-pointer text-sm font-bold text-pine-900">Покажи референтното изчисление</summary>
            <div class="mt-4 grid gap-3 sm:grid-cols-3">
              <div v-for="input in verification.local_breakdown" :key="String(input.organization)" class="rounded-xl bg-paper p-4 text-xs">
                <b>{{ input.organization }}</b>
                <pre class="mt-2 whitespace-pre-wrap font-mono text-[11px] text-mist">{{ JSON.stringify(input, null, 2) }}</pre>
              </div>
            </div>
          </details>
        </div>
        <p v-else class="text-xs text-mist">{{ verificationPrompt() }}</p>
      </div>
    </section>
    <section v-if="activeTab === 'verification' && study.status !== 'COMPLETED'" class="panel mb-4 p-6">
      <h2 class="text-base font-bold">Проверка</h2><p class="mt-2 text-sm text-mist">Проверката става достъпна след успешно завършване на изчислението.</p>
    </section>

    <section v-show="activeTab === 'history'" class="panel p-6">
      <h2 class="mb-4 text-base font-bold">История на действията</h2>
      <div
        v-for="e in audit" :key="e.id"
        class="relative flex gap-3.5 pb-4 last:pb-0 [&:not(:last-child)]:after:absolute [&:not(:last-child)]:after:left-1 [&:not(:last-child)]:after:top-4 [&:not(:last-child)]:after:h-full [&:not(:last-child)]:after:w-px [&:not(:last-child)]:after:bg-line"
      >
        <i class="mt-1.5 size-2 shrink-0 rounded-full bg-pine-500 ring-4 ring-pine-50"></i>
        <div class="leading-snug">
          <b class="block text-xs">{{ tr(e.event_type) }}</b>
          <small class="text-xs text-mist">{{ dateTime(e.created_at) }} · {{ auditActorLabel(e) }}</small>
        </div>
      </div>
    </section>
  </div>
  <div v-else class="grid place-items-center gap-3 py-24 text-pine-600">
    <Spinner :size="30" />
    <p class="text-sm text-mist">Зареждане на проучването…</p>
  </div>
</template>
