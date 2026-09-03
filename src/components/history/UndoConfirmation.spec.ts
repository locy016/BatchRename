import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import UndoConfirmation from './UndoConfirmation.vue'

describe('撤回二次确认', () => {
  it('明确提示整批范围与不覆盖原则', async () => {
    const wrapper = mount(UndoConfirmation, {
      props: { modelValue: true, root: 'D:/资料', total: 6 },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })

    await wrapper.vm.$nextTick()
    expect(document.body.textContent).toContain('6 项')
    expect(document.body.textContent).toContain('不会覆盖现有项目')
    await wrapper.findAllComponents({ name: 'ElButton' }).at(-1)!.trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
    wrapper.unmount()
  })
})
