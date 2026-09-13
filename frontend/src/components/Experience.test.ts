import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Spinner from './Spinner.vue'
import Toaster from './Toaster.vue'
import PasswordInput from './PasswordInput.vue'
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

  it('показва и скрива въведената парола', async () => {
    const wrapper = mount(PasswordInput, { props: { modelValue: 'Тайна123!' } })
    const input = wrapper.get('input')
    const toggle = wrapper.get('button')

    expect(input.attributes('type')).toBe('password')
    expect(toggle.attributes('aria-label')).toBe('Покажи паролата')

    await toggle.trigger('click')
    expect(input.attributes('type')).toBe('text')
    expect(toggle.attributes('aria-label')).toBe('Скрий паролата')

    await toggle.trigger('click')
    expect(input.attributes('type')).toBe('password')
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
