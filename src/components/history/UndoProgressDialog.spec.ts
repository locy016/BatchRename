import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import UndoProgressDialog from './UndoProgressDialog.vue'

describe('撤回进度弹窗', () => {
  it('撤回过程中阻止关闭并显示当前项目', async () => {
    const wrapper = mount(UndoProgressDialog, {
      props: {
        modelValue: true,
        progress: {
          current: 3,
          total: 8,
          path: 'D:/资料/旧名称.txt',
          outcome: '成功',
          detail: '已恢复原名称',
        },
      },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })

    await wrapper.vm.$nextTick()
    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    expect(dialog.props('closeOnClickModal')).toBe(false)
    expect(dialog.props('closeOnPressEscape')).toBe(false)
    expect(dialog.props('showClose')).toBe(false)
    expect(document.body.textContent).toContain('3 / 8')
    expect(document.body.textContent).toContain('旧名称.txt')
    wrapper.unmount()
  })
})
