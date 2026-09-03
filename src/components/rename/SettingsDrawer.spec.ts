import { createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import SettingsDrawer from './SettingsDrawer.vue'

describe('扫描与命名设置', () => {
  it('集中管理扫描对象、扫描层级和扩展名保护', () => {
    const wrapper = mount(SettingsDrawer, {
      props: { modelValue: true },
      global: {
        plugins: [createPinia(), ElementPlus],
        stubs: {
          ElDrawer: { template: '<aside><slot /></aside>' },
        },
      },
    })

    expect(wrapper.text()).toContain('扫描对象')
    expect(wrapper.text()).toContain('扫描层级')
    expect(wrapper.text()).toContain('文件夹名称')
    expect(wrapper.text()).toContain('文件名称')
    expect(wrapper.text()).toContain('扩展名保护')
    expect(wrapper.findComponent({ name: 'ElInputNumber' }).exists()).toBe(true)
  })
})
