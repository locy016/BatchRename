import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import type { UndoCheck } from '../../api/desktop'
import UndoCheckPanel from './UndoCheckPanel.vue'

describe('撤回检查面板', () => {
  it('已撤回记录显示完成反馈且不再提供执行动作', () => {
    const check = {
      operationId: 'completed-operation',
      token: '2026-09-03T10:00:00+08:00',
      state: '已撤回',
      summary: '这次操作已全部撤回，原名称已经恢复。',
      items: [],
    } as UndoCheck
    const wrapper = mount(UndoCheckPanel, {
      props: { check, busy: false },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.text()).toContain('撤回已经完成')
    expect(wrapper.text()).toContain('这次操作已全部撤回，原名称已经恢复。')
    expect(wrapper.text()).not.toContain('待检查')
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
