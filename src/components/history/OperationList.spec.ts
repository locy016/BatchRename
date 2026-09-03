import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import OperationList from './OperationList.vue'

describe('操作日志列表', () => {
  it('同时说明成功、跳过、失败和待撤回数量', () => {
    const wrapper = mount(OperationList, {
      props: {
        loading: false,
        items: [{
          identifier: 'operation-1',
          createdAt: '2026-09-03T10:00:00+08:00',
          updatedAt: '2026-09-03T10:00:01+08:00',
          root: 'D:/资料',
          search: '旧版',
          replacement: '正式',
          status: '部分失败',
          itemCount: 4,
          successCount: 2,
          skippedCount: 1,
          failedCount: 1,
          undoneCount: 0,
          pendingUndoCount: 2,
        }],
      },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.text()).toContain('成功 2')
    expect(wrapper.text()).toContain('跳过 1')
    expect(wrapper.text()).toContain('失败 1')
    expect(wrapper.text()).toContain('待撤回 2')
  })
})
