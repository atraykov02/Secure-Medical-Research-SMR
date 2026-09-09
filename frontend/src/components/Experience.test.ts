import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Spinner from './Spinner.vue'
import Toaster from './Toaster.vue'
import { toast } from '../stores/toast'

describe('интерактивна обратна връзка', () => {
  afterEach(() => {
    vi.useRealTimers()
    for (const item of [...toast.items]) toast.dismiss(item.id)
  })

  it('показва достъпен индикатор за зареждане', () => {
    const wrapper = mount(Spinner, { props: { size: 24 } })
    expect(wrapper.attributes('role')).toBe('status')
    expect(wrapper.attributes('aria-label')).toBe('Зареждане')
  })

  it('показва и автоматично скрива toast известие', async () => {
    vi.useFakeTimers()
    const wrapper = mount(Toaster)
    toast.success('Операцията е успешна.')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Операцията е успешна.')
    vi.advanceTimersByTime(4300)
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).not.toContain('Операцията е успешна.')
  })
})
