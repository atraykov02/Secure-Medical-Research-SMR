<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import type { Audit } from '../types'
import { PageHead } from '../components/Ui.vue'
import { tr, dateTime } from '../i18n'
import Spinner from '../components/Spinner.vue'
import EmptyArt from '../components/art/EmptyArt.vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

const rows = ref<Audit[]>([])
const loading = ref(true)
const page = ref(1)
const pageSize = 10
const totalPages = computed(() => Math.max(1, Math.ceil(rows.value.length / pageSize)))
const visibleRows = computed(() => rows.value.slice((page.value - 1) * pageSize, page.value * pageSize))
const pageNumbers = computed(() => Array.from({ length: totalPages.value }, (_, index) => index + 1))

function goToPage(value: number) {
  page.value = Math.min(Math.max(value, 1), totalPages.value)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function pageButtonClass(value: number): string {
  if (value === page.value) return 'border-pine-600 bg-pine-600 text-white'
  return 'border-line bg-white text-ink hover:border-pine-300 hover:text-pine-700'
}

function pageAriaCurrent(value: number): 'page' | undefined {
  if (value === page.value) return 'page'
  return undefined
}

function actorLabel(event: Audit): string {
  if (event.actor_role === 'ORG_ADMIN') return event.organization_name || event.actor_name || 'Администратор на организация'
  if (event.actor_role === 'RESEARCHER') return `${event.actor_name || 'Изследовател'} · Изследовател`
  if (event.actor_role === 'SYSTEM_ADMIN') return `${event.actor_name || 'Системен администратор'} · Системен администратор`
  return 'Системно действие'
}

onMounted(async () => {
  try { rows.value = (await api.get('/audit')).data }
  finally { loading.value = false }
})
</script>

<template>
  <PageHead eyebrow="Проследимост" title="История на действията" description="Хронология на действията и системните събития, без пациентски данни, локални стойности или тайни дялове." />
  <section class="panel rise p-6">
    <div v-if="loading" class="grid place-items-center py-12 text-pine-600"><Spinner :size="28" /></div>
    <div v-for="event in visibleRows" :key="event.id" class="relative flex gap-3.5 pb-5 last:pb-0 [&:not(:last-child)]:after:absolute [&:not(:last-child)]:after:left-1 [&:not(:last-child)]:after:top-4 [&:not(:last-child)]:after:h-full [&:not(:last-child)]:after:w-px [&:not(:last-child)]:after:bg-line">
      <i class="mt-1.5 size-2 shrink-0 rounded-full bg-pine-500 ring-4 ring-pine-50"></i>
      <div class="min-w-0 grow leading-snug"><b class="block text-[13px]">{{ tr(event.event_type) }}</b><small class="mt-0.5 block text-xs text-mist">{{ dateTime(event.created_at) }} · {{ actorLabel(event) }}</small></div>
      <RouterLink v-if="event.study_id" :to="`/studies/${event.study_id}`" class="shrink-0 text-xs font-semibold text-pine-600 hover:text-pine-700">Виж проучването</RouterLink>
    </div>
    <div v-if="!loading && !rows.length" class="grid place-items-center gap-3 py-8 text-center"><EmptyArt class="w-36" /><p class="text-sm text-mist">Няма записани действия.</p></div>
    <footer v-if="!loading && rows.length > pageSize" class="mt-5 flex flex-col gap-3 border-t border-line pt-5 sm:flex-row sm:items-center sm:justify-between">
      <span class="text-xs text-mist">Страница {{ page }} от {{ totalPages }} · {{ rows.length }} записа</span>
      <nav class="flex flex-wrap items-center gap-1.5" aria-label="Страници на историята">
        <button type="button" class="btn-secondary !p-2" :disabled="page === 1" aria-label="Предишна страница" @click="goToPage(page - 1)"><ChevronLeft :size="16" /></button>
        <button v-for="number in pageNumbers" :key="number" type="button"
          class="grid size-9 cursor-pointer place-items-center rounded-lg border text-xs font-semibold transition"
          :class="pageButtonClass(number)"
          :aria-current="pageAriaCurrent(number)" @click="goToPage(number)">{{ number }}</button>
        <button type="button" class="btn-secondary !p-2" :disabled="page === totalPages" aria-label="Следваща страница" @click="goToPage(page + 1)"><ChevronRight :size="16" /></button>
      </nav>
    </footer>
  </section>
</template>
