<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import type { MPCSession } from '../types'
import { PageHead, StatusBadge } from '../components/Ui.vue'
import { tr, dateTime } from '../i18n'
import Spinner from '../components/Spinner.vue'
import EmptyArt from '../components/art/EmptyArt.vue'

const rows = ref<MPCSession[]>([])
const loading = ref(true)
onMounted(async () => {
  try { rows.value = (await api.get('/mpc-sessions')).data }
  finally { loading.value = false }
})
</script>

<template>
  <PageHead eyebrow="Активност на протокола" title="MPC сесии" description="Оперативен статус без разкриване на дялове или локални агрегати." />
  <section class="panel rise">
    <div v-if="loading" class="grid place-items-center py-16 text-pine-600"><Spinner :size="28" /></div>
    <div v-else class="overflow-x-auto">
      <table class="table-base">
        <thead><tr><th>Проучване</th><th>Параметри</th><th>Статус</th><th>Начало</th></tr></thead>
        <tbody>
          <tr v-for="session in rows" :key="session.id">
            <td><RouterLink :to="`/studies/${session.study_id}`" class="text-[13px] font-semibold text-pine-700 hover:underline">{{ session.study_name }}</RouterLink></td>
            <td class="font-mono text-xs text-ink/70">n={{ session.participant_count }}, t={{ session.threshold }}, {{ tr(session.security_model) }}</td>
            <td><StatusBadge :value="session.status" /></td>
            <td class="text-[13px] text-mist">{{ dateTime(session.started_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="!loading && !rows.length" class="grid place-items-center gap-3 px-6 py-12 text-center"><EmptyArt class="w-40" /><p class="text-sm text-mist">Все още няма стартирани MPC сесии.</p></div>
  </section>
</template>
