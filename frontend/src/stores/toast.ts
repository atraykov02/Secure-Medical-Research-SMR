import { reactive } from 'vue'

export type ToastType = 'success' | 'error' | 'info'
export interface ToastItem { id: number; type: ToastType; text: string }

const items = reactive<ToastItem[]>([])
let seq = 0

function push(type: ToastType, text: string, ms = 4200) {
  const id = ++seq
  items.push({ id, type, text })
  setTimeout(() => dismiss(id), ms)
}

function dismiss(id: number) {
  const i = items.findIndex(t => t.id === id)
  if (i >= 0) items.splice(i, 1)
}

export const toast = {
  items,
  dismiss,
  success: (text: string) => push('success', text),
  error: (text: string) => push('error', text, 6000),
  info: (text: string) => push('info', text)
}
