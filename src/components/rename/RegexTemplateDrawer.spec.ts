import { createPinia } from 'pinia'
import { mount, shallowMount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import RegexTemplateDrawer from './RegexTemplateDrawer.vue'

describe('正则模板抽屉', () => {
  it('使用明确像素宽度避免抽屉在宽屏中溢出', () => {
    const wrapper = mount(RegexTemplateDrawer, {
      props: { modelValue: true },
      global: { plugins: [createPinia(), ElementPlus] },
    })

    expect(wrapper.findComponent({ name: 'ElDrawer' }).props('size')).toBe(460)
  })

  it('在模板窗口统一管理正则模式', async () => {
    const wrapper = mount(RegexTemplateDrawer, {
      props: { modelValue: true },
      global: { plugins: [createPinia(), ElementPlus] },
      attachTo: document.body,
    })

    await wrapper.vm.$nextTick()
    expect(document.body.textContent).toContain('使用正则表达式')
    expect(document.body.querySelector('.el-switch')).not.toBeNull()
    wrapper.unmount()
  })
})
