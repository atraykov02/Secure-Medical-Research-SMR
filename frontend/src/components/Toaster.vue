<script setup lang="ts">
import { toast } from '../stores/toast'
import { CircleCheck, CircleAlert, Info, X } from 'lucide-vue-next'

const icons = { success: CircleCheck, error: CircleAlert, info: Info }
const tone = {
  success: 'border-pine-200 bg-white text-pine-700',
  error: 'border-brick/30 bg-white text-brick',
  info: 'border-line bg-white text-ink'
}
</script>

<template>
  <div class="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2 sm:inset-x-auto sm:right-5 sm:bottom-5" aria-live="polite" aria-atomic="false">
    <TransitionGroup name="toast">
      <div
        v-for="t in toast.items" :key="t.id"
        class="pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-xl border px-4 py-3 shadow-lg shadow-pine-900/10"
        :class="tone[t.type]"
        role="status"
      >
        <component :is="icons[t.type]" :size="18" class="mt-px shrink-0" />
        <p class="grow text-[13px] leading-snug text-ink">{{ t.text }}</p>
        <button class="cursor-pointer rounded p-0.5 text-mist transition hover:text-ink" aria-label="Затвори известието" @click="toast.dismiss(t.id)">
          <X :size="15" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>
