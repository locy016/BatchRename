import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'
import { useRenameStore } from '../../stores/rename'
import WorkflowRail from './WorkflowRail.vue'

describe('重命名流程栏', () => {
  it('在查找输入框按回车触发扫描', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useRenameStore()
    store.root = 'D:/资料'
    store.search = '项目'
    const scan = vi.spyOn(store, 'scan').mockResolvedValue()
    const wrapper = mount(WorkflowRail, {
      global: { plugins: [pinia, ElementPlus] },
    })

    await wrapper.findAll('input')[1].trigger('keyup.enter')

    expect(scan).toHaveBeenCalledOnce()
  })
})
