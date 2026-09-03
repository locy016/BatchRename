import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import { useRenameStore } from '../../stores/rename'
import SearchRuleHint from './SearchRuleHint.vue'

describe('查找规则说明', () => {
  it('普通文本模式说明当前内容和完整扫描条件', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useRenameStore()
    store.search = '旧版'
    store.includeDirs = true
    store.includeFiles = false
    store.maxDepth = 2
    store.renameExtension = false
    const wrapper = mount(SearchRuleHint, { global: { plugins: [pinia, ElementPlus] } })
    const label = wrapper.get('button').attributes('aria-label')

    expect(label).toContain('普通文本')
    expect(label).toContain('旧版')
    expect(label).toContain('文件夹名称')
    expect(label).toContain('2 层')
    expect(label).toContain('保护扩展名')
    expect(label).toContain('项目旧版.docx')
  })

  it('正则模式切换为表达式示例', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useRenameStore()
    store.useRegex = true
    store.search = '^(.+)_副本$'
    const wrapper = mount(SearchRuleHint, { global: { plugins: [pinia, ElementPlus] } })

    expect(wrapper.get('button').attributes('aria-label')).toContain('报告_副本')
  })
})
