<script setup lang="ts">
import { Building2, ChevronDown, ChevronLeft, ChevronRight, Database, Pencil, Plus, RotateCcw, Search, ShieldCheck, SlidersHorizontal, Trash2, X } from 'lucide-vue-next'
import { onMounted, reactive, ref } from 'vue'
import { errorText } from '../api'
import Spinner from '../components/Spinner.vue'
import { PageHead, StatusBadge } from '../components/Ui.vue'
import { createLocalCatalogItem, createLocalPatient, deleteLocalCatalogItem, deleteLocalPatient, getLocalMedicalCatalog, getLocalPatient, getLocalPatients, hospitalAccess, updateLocalCatalogItem, updateLocalPatient } from '../localNode'
import { toast } from '../stores/toast'
import type { HospitalAccess, LocalMedicalCatalog, LocalPatients, LocalPatientWrite } from '../types'

const access = ref<HospitalAccess>()
const patients = ref<LocalPatients>()
const loading = ref(true)
const page = ref(1)
const filtersOpen = ref(false)
const patientDialogOpen = ref(false)
const editingIdentifier = ref<string | null>(null)
const savingPatient = ref(false)
const catalog = ref<LocalMedicalCatalog>()
const filters = reactive({ search: '', min_age: undefined as number | undefined, max_age: undefined as number | undefined, sex: '', disease: '', variant: '', therapy: '', response: '' })
const patientForm = reactive<LocalPatientWrite>({ identifier: '', age: 18, sex: 'F', disease_codes: [], variants: [], treatments: [] })
const diseaseForm = reactive({ code: '', name: '' })
const variantForm = reactive({ code: '', gene: '', chromosome: '', position: 1, reference_allele: '', alternate_allele: '' })
const therapyForm = reactive({ code: '', name: '' })
const responseForm = reactive({ code: '', name: '', is_positive: false })
type CatalogKind = 'diseases' | 'variants' | 'therapies' | 'responses'
const catalogEditing = ref<{ kind: CatalogKind; code: string } | null>(null)
const catalogDeleteTarget = ref<{ kind: CatalogKind; code: string } | null>(null)
const deletingCatalogItem = ref(false)
const catalogDeleteError = ref('')
const patientDeleteTarget = ref<string | null>(null)
const deletingPatient = ref(false)
const patientDeleteError = ref('')

async function load() {
  loading.value = true
  try {
    access.value = await hospitalAccess()
    catalog.value ||= await getLocalMedicalCatalog()
    patients.value = await getLocalPatients(page.value, 20, Object.fromEntries(
      Object.entries(filters).filter(([, value]) => value !== '' && value !== undefined)
    ))
  } catch (e) { toast.error(errorText(e)) }
  finally { loading.value = false }
}
onMounted(load)

function applyFilters() { page.value = 1; load() }
function clearFilters() {
  Object.assign(filters, { search: '', min_age: undefined, max_age: undefined, sex: '', disease: '', variant: '', therapy: '', response: '' })
  applyFilters()
}

function isCatalogItemEditing(kind: CatalogKind): boolean {
  return catalogEditing.value?.kind === kind
}

function catalogActionLabel(kind: CatalogKind): string {
  if (kind === 'variants') {
    if (isCatalogItemEditing(kind)) return 'Запази варианта'
    return 'Добави вариант'
  }
  if (isCatalogItemEditing(kind)) return 'Запази'
  return 'Добави'
}

function responsePolarityLabel(isPositive: boolean): string {
  if (isPositive) return 'положителен'
  return 'неположителен'
}

function filtersChevronClass(): string {
  if (filtersOpen.value) return 'rotate-180'
  return ''
}

function patientDialogTitle(): string {
  if (editingIdentifier.value) return 'Редактиране на пациент'
  return 'Добавяне на пациент'
}

function patientSubmitLabel(): string {
  if (editingIdentifier.value) return 'Запази промените'
  return 'Добави пациента'
}

function openCreatePatient() {
  editingIdentifier.value = null
  Object.assign(patientForm, { identifier: '', age: 18, sex: 'F', disease_codes: [], variants: [], treatments: [] })
  patientDialogOpen.value = true
}

async function openEditPatient(identifier: string) {
  try {
    const patient = await getLocalPatient(identifier)
    editingIdentifier.value = identifier
    Object.assign(patientForm, {
      identifier: patient.identifier,
      age: patient.age,
      sex: patient.sex,
      disease_codes: [...patient.disease_codes],
      variants: patient.variants.map(item => ({ ...item })),
      treatments: patient.treatments.map(item => ({ ...item })),
    })
    patientDialogOpen.value = true
  } catch (e) { toast.error(errorText(e)) }
}

function patientPayload(): LocalPatientWrite {
  return {
    identifier: patientForm.identifier.trim(), age: patientForm.age, sex: patientForm.sex,
    disease_codes: [...patientForm.disease_codes],
    variants: patientForm.variants.map(item => ({ ...item })),
    treatments: patientForm.treatments.map(item => ({ ...item })),
  }
}

function addDisease() {
  const code = catalog.value?.diseases.find(item => !patientForm.disease_codes.includes(item.code))?.code
  if (code) patientForm.disease_codes.push(code)
}
function addVariant() {
  const code = catalog.value?.variants.find(item => !patientForm.variants.some(value => value.code === item.code))?.code
  if (code) patientForm.variants.push({ code, genotype: '0/1' })
}
function addTreatment() {
  const therapy_code = catalog.value?.therapies.find(item => !patientForm.treatments.some(value => value.therapy_code === item.code))?.code
  const response = catalog.value?.responses.find(item => !item.is_positive)?.code || catalog.value?.responses[0]?.code
  if (therapy_code && response) patientForm.treatments.push({ therapy_code, response })
}

async function addCatalogItem(kind: CatalogKind, payload: Record<string, unknown>) {
  try {
    if (catalogEditing.value?.kind === kind) await updateLocalCatalogItem(kind, catalogEditing.value.code, payload)
    else await createLocalCatalogItem(kind, payload)
    catalog.value = await getLocalMedicalCatalog()
    if (kind === 'diseases') Object.assign(diseaseForm, { code: '', name: '' })
    if (kind === 'variants') Object.assign(variantForm, { code: '', gene: '', chromosome: '', position: 1, reference_allele: '', alternate_allele: '' })
    if (kind === 'therapies') Object.assign(therapyForm, { code: '', name: '' })
    if (kind === 'responses') Object.assign(responseForm, { code: '', name: '', is_positive: false })
    toast.success(catalogEditing.value ? 'Стойността е редактирана.' : 'Стойността е добавена в локалната конфигурация.')
    catalogEditing.value = null
  } catch (e) { toast.error(errorText(e)) }
}

function editCatalogItem(kind: CatalogKind, item: Record<string, unknown>) {
  catalogEditing.value = { kind, code: String(item.code) }
  if (kind === 'diseases') Object.assign(diseaseForm, { code: item.code, name: item.name })
  if (kind === 'variants') Object.assign(variantForm, item)
  if (kind === 'therapies') Object.assign(therapyForm, { code: item.code, name: item.name })
  if (kind === 'responses') Object.assign(responseForm, { code: item.code, name: item.name, is_positive: item.is_positive })
}

function removeCatalogItem(kind: CatalogKind, code: string) {
  catalogDeleteError.value = ''
  catalogDeleteTarget.value = { kind, code }
}

async function confirmCatalogItemRemoval() {
  if (!catalogDeleteTarget.value) return
  deletingCatalogItem.value = true
  catalogDeleteError.value = ''
  try {
    await deleteLocalCatalogItem(catalogDeleteTarget.value.kind, catalogDeleteTarget.value.code)
    catalog.value = await getLocalMedicalCatalog()
    catalogDeleteTarget.value = null
    toast.success('Стойността е изтрита от локалната конфигурация.')
  } catch (e) { catalogDeleteError.value = errorText(e) }
  finally { deletingCatalogItem.value = false }
}

async function savePatient() {
  savingPatient.value = true
  try {
    const payload = patientPayload()
    if (editingIdentifier.value) await updateLocalPatient(editingIdentifier.value, payload)
    else await createLocalPatient(payload)
    toast.success(editingIdentifier.value ? 'Пациентът е редактиран.' : 'Пациентът е добавен.')
    patientDialogOpen.value = false
    page.value = 1
    await load()
  } catch (e) { toast.error(errorText(e)) }
  finally { savingPatient.value = false }
}

function removePatient(identifier: string) {
  patientDeleteError.value = ''
  patientDeleteTarget.value = identifier
}

async function confirmPatientRemoval() {
  if (!patientDeleteTarget.value) return
  deletingPatient.value = true
  patientDeleteError.value = ''
  try {
    await deleteLocalPatient(patientDeleteTarget.value)
    patientDeleteTarget.value = null
    toast.success('Пациентът е изтрит от локалната база.')
    await load()
  } catch (e) { patientDeleteError.value = errorText(e) }
  finally { deletingPatient.value = false }
}
</script>

<template>
  <div>
    <PageHead eyebrow="Моята организация" :title="access?.organization.name || 'Организационен профил'" />
    <div v-if="loading" class="grid place-items-center py-24 text-pine-600"><Spinner :size="30" /></div>
    <template v-else-if="access && patients">
      <section class="mb-5 grid gap-4 md:grid-cols-3">
        <article class="metric-card"><Building2 :size="20" class="text-pine-600" /><span class="mt-5 block text-xs text-mist">MPC участник</span><b class="mt-1 block text-2xl">P{{ access.organization.participant_index }}</b></article>
        <article class="metric-card"><ShieldCheck :size="20" class="text-pine-600" /><span class="mt-5 block text-xs text-mist">Статус на възела</span><div class="mt-2"><StatusBadge value="READY" /></div></article>
        <article class="metric-card"><Database :size="20" class="text-pine-600" /><span class="mt-5 block text-xs text-mist">Локални записи</span><b class="mt-1 block text-2xl">{{ patients.total }}</b></article>
      </section>

      <details class="panel mb-5 overflow-hidden">
        <summary class="flex cursor-pointer items-center justify-between px-6 py-5 text-sm font-bold">
          <span>Конфигурация</span><span class="text-xs font-normal text-mist">Заболявания, варианти, терапии и отговори</span>
        </summary>
        <div class="grid gap-4 border-t border-line bg-white/60 p-5 lg:grid-cols-2">
          <form class="rounded-xl border border-line bg-white p-4" @submit.prevent="addCatalogItem('diseases', diseaseForm)">
            <h3 class="font-bold">Ново заболяване</h3>
            <div class="mt-3 grid gap-2 sm:grid-cols-[10rem_1fr_auto]"><input v-model="diseaseForm.code" required placeholder="Код, напр. DX-CARDIO"><input v-model="diseaseForm.name" required placeholder="Наименование"><button class="btn-primary"><Plus v-if="!isCatalogItemEditing('diseases')" :size="16" />{{ catalogActionLabel('diseases') }}</button></div>
            <div class="mt-3 grid gap-1.5"><div v-for="item in catalog?.diseases" :key="item.code" class="flex items-center gap-2 rounded-lg bg-paper px-3 py-2 text-xs"><span class="grow"><b>{{ item.code }}</b> · {{ item.name }}</span><button type="button" class="btn-secondary !p-1.5" @click="editCatalogItem('diseases', item)"><Pencil :size="13" /></button><button type="button" class="btn-danger !p-1.5" @click="removeCatalogItem('diseases', item.code)"><Trash2 :size="13" /></button></div></div>
          </form>

          <form class="rounded-xl border border-line bg-white p-4" @submit.prevent="addCatalogItem('therapies', therapyForm)">
            <h3 class="font-bold">Нова терапия</h3>
            <div class="mt-3 grid gap-2 sm:grid-cols-[10rem_1fr_auto]"><input v-model="therapyForm.code" required placeholder="Код, напр. THERAPY-C"><input v-model="therapyForm.name" required placeholder="Наименование"><button class="btn-primary"><Plus v-if="!isCatalogItemEditing('therapies')" :size="16" />{{ catalogActionLabel('therapies') }}</button></div>
            <div class="mt-3 grid gap-1.5"><div v-for="item in catalog?.therapies" :key="item.code" class="flex items-center gap-2 rounded-lg bg-paper px-3 py-2 text-xs"><span class="grow"><b>{{ item.code }}</b> · {{ item.name }}</span><button type="button" class="btn-secondary !p-1.5" @click="editCatalogItem('therapies', item)"><Pencil :size="13" /></button><button type="button" class="btn-danger !p-1.5" @click="removeCatalogItem('therapies', item.code)"><Trash2 :size="13" /></button></div></div>
          </form>

          <form class="rounded-xl border border-line bg-white p-4 lg:col-span-2" @submit.prevent="addCatalogItem('variants', variantForm)">
            <h3 class="font-bold">Нов генетичен вариант</h3>
            <div class="mt-3 grid gap-2 md:grid-cols-3">
              <input v-model="variantForm.code" required placeholder="Код, напр. VAR-C"><input v-model="variantForm.gene" required placeholder="Ген"><input v-model="variantForm.chromosome" required placeholder="Хромозома">
              <input v-model.number="variantForm.position" type="number" min="1" required placeholder="Позиция"><input v-model="variantForm.reference_allele" required placeholder="Референтен алел"><input v-model="variantForm.alternate_allele" required placeholder="Алтернативен алел">
            </div>
            <div class="mt-3 flex justify-end"><button class="btn-primary"><Plus v-if="!isCatalogItemEditing('variants')" :size="16" />{{ catalogActionLabel('variants') }}</button></div>
            <div class="mt-3 grid gap-1.5"><div v-for="item in catalog?.variants" :key="item.code" class="flex items-center gap-2 rounded-lg bg-paper px-3 py-2 text-xs"><span class="grow"><b>{{ item.code }}</b> · {{ item.name }} · {{ item.reference_allele }}→{{ item.alternate_allele }}</span><button type="button" class="btn-secondary !p-1.5" @click="editCatalogItem('variants', item)"><Pencil :size="13" /></button><button type="button" class="btn-danger !p-1.5" @click="removeCatalogItem('variants', item.code)"><Trash2 :size="13" /></button></div></div>
          </form>

          <form class="rounded-xl border border-line bg-white p-4 lg:col-span-2" @submit.prevent="addCatalogItem('responses', responseForm)">
            <h3 class="font-bold">Нова категория терапевтичен отговор</h3>
            <div class="mt-3 grid items-center gap-2 md:grid-cols-[11rem_1fr_auto_auto]">
              <input v-model="responseForm.code" required placeholder="Код"><input v-model="responseForm.name" required placeholder="Наименование">
              <label class="flex items-center gap-2 text-left text-xs"><input v-model="responseForm.is_positive" type="checkbox" class="!size-4 accent-pine-600"> Положителен отговор</label>
              <button class="btn-primary"><Plus v-if="!isCatalogItemEditing('responses')" :size="16" />{{ catalogActionLabel('responses') }}</button>
            </div>
            <p class="mt-2 text-xs text-mist">Положителните категории се броят като отговорили пациенти в MPC анализите.</p>
            <div class="mt-3 grid gap-1.5"><div v-for="item in catalog?.responses" :key="item.code" class="flex items-center gap-2 rounded-lg bg-paper px-3 py-2 text-xs"><span class="grow"><b>{{ item.code }}</b> · {{ item.name }} · {{ responsePolarityLabel(item.is_positive) }}</span><button type="button" class="btn-secondary !p-1.5" @click="editCatalogItem('responses', item)"><Pencil :size="13" /></button><button type="button" class="btn-danger !p-1.5" @click="removeCatalogItem('responses', item.code)"><Trash2 :size="13" /></button></div></div>
          </form>
        </div>
      </details>

      <section class="panel overflow-hidden">
        <header class="flex flex-col gap-3 border-b border-line px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div><h2 class="section-title">Синтетични медицински данни</h2><p class="mt-1 text-xs text-mist">Съхраняват се локално в {{ patients.organization }} · Не се предават към централния координатор</p></div>
          <div class="flex items-center gap-2">
            <span class="rounded-full bg-pine-50 px-3 py-1.5 text-xs font-semibold text-pine-700">Локално хранилище</span>
            <button type="button" class="btn-primary" @click="openCreatePatient"><Plus :size="16" /> Добави пациент</button>
          </div>
        </header>
        <div class="border-b border-line bg-white/60 p-4 sm:p-5">
          <button type="button" class="flex w-full items-center gap-2 text-left text-sm font-bold" :aria-expanded="filtersOpen" aria-controls="patient-filters" @click="filtersOpen = !filtersOpen">
            <SlidersHorizontal :size="16" class="text-pine-600" />
            <span class="grow">Филтри</span>
            <ChevronDown :size="18" class="text-mist transition-transform duration-200" :class="filtersChevronClass()" />
          </button>
          <Transition name="filter-panel">
            <form v-if="filtersOpen" id="patient-filters" class="pt-4" @submit.prevent="applyFilters">
          <div class="mb-3 flex items-center justify-end"><button type="button" class="flex items-center gap-1.5 text-xs font-semibold text-mist hover:text-pine-700" @click="clearFilters"><RotateCcw :size="13" /> Изчисти</button></div>
          <div class="grid gap-3 md:grid-cols-4">
            <label class="relative md:col-span-2"><Search :size="15" class="absolute left-3 top-3 text-mist" /><input v-model="filters.search" class="!pl-9" placeholder="Идентификатор на пациент"></label>
            <input v-model.number="filters.min_age" type="number" min="0" max="130" placeholder="Мин. възраст">
            <input v-model.number="filters.max_age" type="number" min="0" max="130" placeholder="Макс. възраст">
            <select v-model="filters.sex"><option value="">Всички полове</option><option value="F">Жени</option><option value="M">Мъже</option></select>
            <input v-model="filters.disease" placeholder="Заболяване, напр. DX-LUNG">
            <input v-model="filters.variant" placeholder="Вариант, напр. VAR-A">
            <input v-model="filters.therapy" placeholder="Терапия, напр. THERAPY-A">
            <select v-model="filters.response"><option value="">Всички отговори</option><option value="RESPONDER">Responder</option><option value="NON_RESPONDER">Non-responder</option></select>
            <button class="btn-primary md:col-start-4"><Search :size="15" /> Приложи филтрите</button>
          </div>
            </form>
          </Transition>
        </div>
        <div class="overflow-x-auto">
          <table class="table-base">
            <thead><tr><th>Пациент</th><th>Възраст</th><th>Пол</th><th>Заболяване</th><th>Вариант</th><th>Терапия</th><th>Отговор</th><th class="text-right">Действия</th></tr></thead>
            <tbody><tr v-for="p in patients.items" :key="p.identifier">
              <td><b class="font-mono text-xs">{{ p.identifier }}</b></td><td>{{ p.age }}</td><td>{{ p.sex }}</td>
              <td>{{ p.diseases.join(', ') || '—' }}</td><td>{{ p.variants.join(', ') || 'Няма' }}</td>
              <td>{{ p.therapies.join(', ') || '—' }}</td><td>{{ p.responses.join(', ') || '—' }}</td>
              <td><div class="flex justify-end gap-1">
                <button type="button" class="btn-secondary !p-2" :aria-label="`Редактиране на ${p.identifier}`" @click="openEditPatient(p.identifier)"><Pencil :size="14" /></button>
                <button type="button" class="btn-danger !p-2" :aria-label="`Изтриване на ${p.identifier}`" @click="removePatient(p.identifier)"><Trash2 :size="14" /></button>
              </div></td>
            </tr></tbody>
          </table>
          <div v-if="!patients.items.length" class="grid place-items-center py-14 text-sm text-mist">Няма записи, отговарящи на избраните филтри.</div>
        </div>
        <footer class="flex items-center justify-between border-t border-line px-6 py-4">
          <span class="text-xs text-mist">Страница {{ patients.page }} · {{ patients.total }} записа</span>
          <div class="flex gap-2">
            <button class="btn-secondary !p-2" :disabled="page === 1" aria-label="Предишна страница" @click="page--; load()"><ChevronLeft :size="16" /></button>
            <button class="btn-secondary !p-2" :disabled="page * patients.page_size >= patients.total" aria-label="Следваща страница" @click="page++; load()"><ChevronRight :size="16" /></button>
          </div>
        </footer>
      </section>
    </template>

    <Teleport to="body">
      <div v-if="catalogDeleteTarget" class="fixed inset-0 z-50 grid place-items-center bg-pine-950/55 p-4 backdrop-blur-sm" @click.self="catalogDeleteTarget = null">
        <section class="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="catalog-delete-title">
          <header class="flex items-center justify-between border-b border-line px-6 py-5">
            <h2 id="catalog-delete-title" class="text-lg font-bold">Изтриване на стойност</h2>
            <button type="button" class="grid size-9 place-items-center rounded-lg text-mist hover:bg-paper hover:text-ink" aria-label="Затвори" :disabled="deletingCatalogItem" @click="catalogDeleteTarget = null"><X :size="20" /></button>
          </header>
          <div class="px-6 py-5">
            <p class="text-sm leading-6 text-ink">Сигурни ли сте, че искате да изтриете конфигурационната стойност <b>{{ catalogDeleteTarget.code }}</b>?</p>
            <div v-if="catalogDeleteError" class="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-5 text-red-700" role="alert">{{ catalogDeleteError }}</div>
          </div>
          <footer class="flex justify-end gap-2 border-t border-line px-6 py-4">
            <button type="button" class="btn-secondary" :disabled="deletingCatalogItem" @click="catalogDeleteTarget = null">Отказ</button>
            <button type="button" class="btn-danger" :disabled="deletingCatalogItem" @click="confirmCatalogItemRemoval"><Spinner v-if="deletingCatalogItem" :size="16" /><Trash2 v-else :size="16" /> Изтрий</button>
          </footer>
        </section>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="patientDeleteTarget" class="fixed inset-0 z-50 grid place-items-center bg-pine-950/55 p-4 backdrop-blur-sm" @click.self="patientDeleteTarget = null">
        <section class="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="patient-delete-title">
          <header class="flex items-center justify-between border-b border-line px-6 py-5">
            <h2 id="patient-delete-title" class="text-lg font-bold">Изтриване на пациент</h2>
            <button type="button" class="grid size-9 place-items-center rounded-lg text-mist hover:bg-paper hover:text-ink" aria-label="Затвори" :disabled="deletingPatient" @click="patientDeleteTarget = null"><X :size="20" /></button>
          </header>
          <div class="px-6 py-5">
            <p class="text-sm leading-6 text-ink">Сигурни ли сте, че искате да изтриете пациент <b>{{ patientDeleteTarget }}</b>?</p>
            <p class="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold leading-5 text-red-700">Действието е необратимо и пациентският запис ще бъде премахнат от локалната база на болницата.</p>
            <div v-if="patientDeleteError" class="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-5 text-red-700" role="alert">{{ patientDeleteError }}</div>
          </div>
          <footer class="flex justify-end gap-2 border-t border-line px-6 py-4">
            <button type="button" class="btn-secondary" :disabled="deletingPatient" @click="patientDeleteTarget = null">Отказ</button>
            <button type="button" class="btn-danger" :disabled="deletingPatient" @click="confirmPatientRemoval"><Spinner v-if="deletingPatient" :size="16" /><Trash2 v-else :size="16" /> Изтрий</button>
          </footer>
        </section>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="patientDialogOpen" class="fixed inset-0 z-50 grid place-items-center bg-pine-950/55 p-4 backdrop-blur-sm" @click.self="patientDialogOpen = false">
        <form class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl" @submit.prevent="savePatient">
          <header class="sticky top-0 flex items-center justify-between border-b border-line bg-white px-6 py-5">
            <div><span class="text-xs font-semibold text-pine-600">Локална пациентска база</span><h2 class="mt-1 text-lg font-bold">{{ patientDialogTitle() }}</h2></div>
            <button type="button" class="grid size-9 place-items-center rounded-lg text-mist hover:bg-paper hover:text-ink" aria-label="Затвори" @click="patientDialogOpen = false"><X :size="20" /></button>
          </header>
          <div class="grid gap-x-4 p-6 sm:grid-cols-2">
            <label class="field !mt-0">Идентификатор<input v-model="patientForm.identifier" required minlength="3" placeholder="H4-SYN-000501"></label>
            <label class="field !mt-0">Възраст<input v-model.number="patientForm.age" type="number" min="0" max="130" required></label>
            <label class="field">Пол<select v-model="patientForm.sex"><option value="F">Жена</option><option value="M">Мъж</option></select></label>
            <div class="sm:col-span-2">
              <div class="mb-2 flex items-center justify-between"><b class="text-[13px]">Заболявания</b><button type="button" class="btn-secondary !px-2.5 !py-1.5 !text-xs" @click="addDisease"><Plus :size="13" /> Добави</button></div>
              <div v-if="patientForm.disease_codes.length" class="grid gap-2">
                <div v-for="(_, index) in patientForm.disease_codes" :key="index" class="flex gap-2">
                  <select v-model="patientForm.disease_codes[index]" class="grow">
                    <option v-for="item in catalog?.diseases" :key="item.code" :value="item.code" :disabled="patientForm.disease_codes.includes(item.code) && patientForm.disease_codes[index] !== item.code">{{ item.code }} — {{ item.name }}</option>
                  </select>
                  <button type="button" class="btn-danger !p-2.5" aria-label="Премахни заболяването" @click="patientForm.disease_codes.splice(index, 1)"><Trash2 :size="15" /></button>
                </div>
              </div>
              <p v-else class="rounded-lg border border-dashed border-line p-3 text-xs text-mist">Няма свързано заболяване.</p>
            </div>

            <div class="mt-4 sm:col-span-2">
              <div class="mb-2 flex items-center justify-between"><b class="text-[13px]">Генетични варианти</b><button type="button" class="btn-secondary !px-2.5 !py-1.5 !text-xs" @click="addVariant"><Plus :size="13" /> Добави</button></div>
              <div v-if="patientForm.variants.length" class="grid gap-2">
                <div v-for="(variant, index) in patientForm.variants" :key="index" class="grid grid-cols-[1fr_8rem_auto] gap-2">
                  <select v-model="variant.code"><option v-for="item in catalog?.variants" :key="item.code" :value="item.code" :disabled="patientForm.variants.some(value => value.code === item.code) && variant.code !== item.code">{{ item.code }} — {{ item.name }}</option></select>
                  <select v-model="variant.genotype"><option v-for="genotype in catalog?.genotypes" :key="genotype" :value="genotype">{{ genotype }}</option></select>
                  <button type="button" class="btn-danger !p-2.5" aria-label="Премахни варианта" @click="patientForm.variants.splice(index, 1)"><Trash2 :size="15" /></button>
                </div>
              </div>
              <p v-else class="rounded-lg border border-dashed border-line p-3 text-xs text-mist">Няма свързан генетичен вариант.</p>
            </div>

            <div class="mt-4 sm:col-span-2">
              <div class="mb-2 flex items-center justify-between"><b class="text-[13px]">Терапии и отговори</b><button type="button" class="btn-secondary !px-2.5 !py-1.5 !text-xs" @click="addTreatment"><Plus :size="13" /> Добави</button></div>
              <div v-if="patientForm.treatments.length" class="grid gap-2">
                <div v-for="(treatment, index) in patientForm.treatments" :key="index" class="grid grid-cols-[1fr_11rem_auto] gap-2">
                  <select v-model="treatment.therapy_code"><option v-for="item in catalog?.therapies" :key="item.code" :value="item.code" :disabled="patientForm.treatments.some(value => value.therapy_code === item.code) && treatment.therapy_code !== item.code">{{ item.code }} — {{ item.name }}</option></select>
                  <select v-model="treatment.response"><option v-for="response in catalog?.responses" :key="response.code" :value="response.code">{{ response.name }} ({{ response.code }})</option></select>
                  <button type="button" class="btn-danger !p-2.5" aria-label="Премахни терапията" @click="patientForm.treatments.splice(index, 1)"><Trash2 :size="15" /></button>
                </div>
              </div>
              <p v-else class="rounded-lg border border-dashed border-line p-3 text-xs text-mist">Няма свързана терапия.</p>
            </div>
          </div>
          <footer class="flex justify-end gap-2 border-t border-line px-6 py-4">
            <button type="button" class="btn-secondary" @click="patientDialogOpen = false">Отказ</button>
            <button class="btn-primary" :disabled="savingPatient"><Spinner v-if="savingPatient" :size="16" /> {{ patientSubmitLabel() }}</button>
          </footer>
        </form>
      </div>
    </Teleport>
  </div>
</template>
