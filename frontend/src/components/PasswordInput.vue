<script setup lang="ts">
import { ref } from 'vue'
import { Eye, EyeOff } from 'lucide-vue-next'

withDefaults(defineProps<{
  autocomplete?: string
  minlength?: number
  required?: boolean
}>(), {
  autocomplete: undefined,
  minlength: undefined,
  required: false
})

const model = defineModel<string>({ required: true })
const visible = ref(false)
</script>

<template>
  <div class="relative">
    <input
      v-model="model"
      :type="visible ? 'text' : 'password'"
      :autocomplete="autocomplete"
      :minlength="minlength"
      :required="required"
      class="!pr-11"
    >
    <button
      type="button"
      class="absolute inset-y-0 right-0 grid w-11 cursor-pointer place-items-center rounded-r-lg text-mist transition hover:text-pine-700 focus-visible:z-10"
      :aria-label="visible ? 'Скрий паролата' : 'Покажи паролата'"
      :aria-pressed="visible"
      :title="visible ? 'Скрий паролата' : 'Покажи паролата'"
      @click="visible = !visible"
    >
      <EyeOff v-if="visible" :size="18" aria-hidden="true" />
      <Eye v-else :size="18" aria-hidden="true" />
    </button>
  </div>
</template>
