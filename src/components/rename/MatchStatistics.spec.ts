import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { useRenameStore } from '../../stores/rename'
import MatchStatistics from './MatchStatistics.vue'

describe('结果统计栏', () => {
  it('目录浏览状态说明根目录项目数量', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useRenameStore()
    store.resultMode = 'directory'
    store.rootTotal = 12
    store.rootItems = [
      { source: 'D:/资料/目录', kind: '文件夹' },
      { source: 'D:/资料/文件.txt', kind: '文件' },
    ]
    const wrapper = mount(MatchStatistics, { global: { plugins: [pinia] } })

    expect(wrapper.text()).toContain('根目录内容：12 项')
    expect(wrapper.text()).toContain('当前显示：2 项')
    expect(wrapper.text()).not.toContain('匹配：')
  })
})
