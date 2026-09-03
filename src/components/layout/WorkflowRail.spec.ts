import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'
import { useRenameStore } from '../../stores/rename'
import WorkflowRail from './WorkflowRail.vue'

describe('重命名流程栏', () => {
  it('使用紧凑的四步流程且不显示脱离情境的说明', () => {
    const pinia = createPinia()
    const wrapper = mount(WorkflowRail, {
      global: { plugins: [pinia, ElementPlus] },
    })

    expect(wrapper.findAll('ol > li')).toHaveLength(4)
    expect(wrapper.text()).not.toContain('完成预览后才会允许执行')
    expect(wrapper.text()).not.toContain('扫描范围')
    expect(wrapper.text()).toContain('1　选择目录')
    expect(wrapper.text()).toContain('2　查找内容')
    expect(wrapper.text()).toContain('3　替换与预览')
    expect(wrapper.text()).toContain('4　确认执行')
  })

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

  it('在替换输入框按回车生成结果预览', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useRenameStore()
    store.scanJobId = 'scan-job'
    const preview = vi.spyOn(store, 'preview').mockResolvedValue()
    const wrapper = mount(WorkflowRail, {
      global: { plugins: [pinia, ElementPlus] },
    })

    await wrapper.get('input[placeholder="可留空以删除匹配片段"]').trigger('keyup.enter')

    expect(preview).toHaveBeenCalledOnce()
  })
})
