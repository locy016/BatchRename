import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import type { UndoCheck } from '../../api/desktop'
import type { OperationLogV1 } from '../../types/contracts'
import OperationDetails from './OperationDetails.vue'

const operation = {
  schema_version: 1,
  identifier: 'operation-1',
  created_at: '2026-09-03T10:00:00+08:00',
  updated_at: '2026-09-03T10:00:00+08:00',
  root: 'D:/资料',
  search: '旧版',
  replacement: '正式',
  use_regex: false,
  max_depth: null,
  include_files: true,
  include_dirs: true,
  rename_extension: false,
  status: '已完成',
  items: [],
  error: '',
} as OperationLogV1

const readyCheck = {
  operationId: 'operation-1',
  token: 'token-1',
  state: '可撤回',
  summary: '检查通过，可撤回 1 项。',
  items: [],
} as UndoCheck

describe('操作日志详情', () => {
  it('在同一工作区显示撤回检查并触发整批撤回', async () => {
    const wrapper = mount(OperationDetails, {
      props: { operation, undoCheck: readyCheck, busy: false, undoError: '' },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.text()).toContain('撤回操作')
    expect(wrapper.text()).toContain('检查通过，可撤回 1 项。')
    await wrapper.get('[data-testid="execute-undo"]').trigger('click')
    expect(wrapper.emitted('undo')).toHaveLength(1)
  })

  it('已撤回记录只显示完成状态，不再提供执行按钮', () => {
    const wrapper = mount(OperationDetails, {
      props: {
        operation: { ...operation, status: '已撤回' },
        undoCheck: { ...readyCheck, state: '已撤回', summary: '原名称已经恢复。' },
        busy: false,
        undoError: '',
      },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.text()).toContain('原名称已经恢复。')
    expect(wrapper.find('[data-testid="execute-undo"]').exists()).toBe(false)
  })
})
