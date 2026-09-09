import {mount} from '@vue/test-utils'
import {describe,expect,it} from 'vitest'
import {PageHead,StatusBadge} from './Ui.vue'

describe('български интерфейс',()=>{
  it('показва преведен статус на протокола',()=>{
    const wrapper=mount(StatusBadge,{props:{value:'WAITING_APPROVAL'}})
    expect(wrapper.text()).toBe('Очаква одобрение')
    expect(wrapper.classes()).toContain('s-waiting_approval')
  })

  it('показва заглавие и действие',()=>{
    const wrapper=mount(PageHead,{props:{eyebrow:'Изследвания',title:'Проучвания',description:'Защитени анализи'},slots:{default:'Действие'}})
    expect(wrapper.text()).toContain('Проучвания')
    expect(wrapper.text()).toContain('Действие')
  })
})
