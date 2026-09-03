import { createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import ExecutionProgressDialog from './ExecutionProgressDialog.vue'

describe('文件名处理进度弹窗', () => {
  it('执行过程中禁止关闭并显示逐项进度', async () => {
    const wrapper = mount(ExecutionProgressDialog, {
      props: {
        modelValue: true,
        progress: {
          current: 3,
          total: 8,
          relativePath: '资料/报告.txt',
          outcome: '成功',
          detail: '文件名已经更新',
        },
      },
      global: { plugins: [createPinia(), ElementPlus] },
      attachTo: document.body,
    })

    await wrapper.vm.$nextTick()
    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    expect(dialog.props('closeOnClickModal')).toBe(false)
    expect(dialog.props('closeOnPressEscape')).toBe(false)
    expect(dialog.props('showClose')).toBe(false)
    expect(dialog.props('title')).toBe('正在处理文件名')
    expect(document.body.textContent).toContain('3 / 8')
    expect(document.body.textContent).toContain('资料/报告.txt')
    wrapper.unmount()
  })
})
