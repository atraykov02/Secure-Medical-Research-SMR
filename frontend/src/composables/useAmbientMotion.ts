import { onMounted, onUnmounted, type Ref } from 'vue'

export function useAmbientMotion(target: Ref<HTMLElement | null>) {
  let frame = 0
  let reduceMotion: MediaQueryList

  const update = (event: PointerEvent) => {
    if (!target.value || reduceMotion.matches) return
    cancelAnimationFrame(frame)
    frame = requestAnimationFrame(() => {
      const x = event.clientX / window.innerWidth - 0.5
      const y = event.clientY / window.innerHeight - 0.5
      target.value?.style.setProperty('--ambient-x', `${x * 22}px`)
      target.value?.style.setProperty('--ambient-y', `${y * 18}px`)
      target.value?.style.setProperty('--ambient-x-reverse', `${x * -15}px`)
      target.value?.style.setProperty('--ambient-y-reverse', `${y * -12}px`)
      target.value?.style.setProperty('--ambient-x-soft', `${x * 10}px`)
      target.value?.style.setProperty('--ambient-y-soft', `${y * 8}px`)
    })
  }

  onMounted(() => {
    reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    window.addEventListener('pointermove', update, { passive: true })
  })

  onUnmounted(() => {
    cancelAnimationFrame(frame)
    window.removeEventListener('pointermove', update)
  })
}
