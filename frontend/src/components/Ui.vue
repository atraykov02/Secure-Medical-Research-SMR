<script lang="ts">
import { defineComponent, h } from 'vue'
import { tr } from '../i18n'

const dot: Record<string, string> = {
  completed: 'bg-pine-500',
  approved: 'bg-pine-500',
  ready: 'bg-sky-600',
  waiting_approval: 'bg-amber-500',
  invited: 'bg-amber-500',
  sharing: 'bg-amber-500',
  computing: 'bg-pine-400 animate-pulse',
  reconstructing: 'bg-pine-400 animate-pulse',
  created: 'bg-slate-400',
  draft: 'bg-slate-400',
  destroyed: 'bg-slate-400',
  failed: 'bg-brick',
  rejected: 'bg-brick'
}

export const StatusBadge = defineComponent({
  props: { value: { type: String, required: true } },
  setup(p) {
    return () => {
      const key = p.value.toLowerCase()
      return h('span', {
        class: ['s-' + key, 'inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium text-ink/80']
      }, [
        h('i', { class: ['size-1.5 rounded-full', dot[key] || 'bg-slate-400'] }),
        tr(p.value)
      ])
    }
  }
})

export const PageHead = defineComponent({
  props: { eyebrow: String, title: String, description: String },
  setup(p, { slots }) {
    return () => h('header', { class: 'mb-8 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between' }, [
      h('div', { class: 'max-w-2xl' }, [
        p.eyebrow && h('p', { class: 'mb-1.5 text-[13px] font-medium text-pine-600' }, p.eyebrow),
        h('h1', { class: 'text-[28px] font-bold leading-tight tracking-tight' }, p.title),
        p.description && h('span', { class: 'sr-only' }, p.description)
      ]),
      h('div', { class: 'flex shrink-0 items-center gap-2.5' }, slots.default?.())
    ])
  }
})

export default defineComponent({ name: 'UiExports' })
</script>
