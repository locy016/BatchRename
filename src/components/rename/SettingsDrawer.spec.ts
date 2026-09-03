import { createPinia } from 'pinia'
import { mount, shallowMount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import { useRenameStore } from '../../stores/rename'
import SettingsDrawer from './SettingsDrawer.vue'

describe('扫描与命名设置', () => {
  it('使用明确像素宽度避免抽屉在宽屏中溢出', () => {
    const wrapper = shallowMount(SettingsDrawer, {
      props: { modelValue: true },
      global: { plugins: [createPinia(), ElementPlus] },
    })

    expect(wrapper.findComponent({ name: 'ElDrawer' }).props('size')).toBe(420)
  })

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

  it('结果显示支持任意正整数或全部且默认一百条', () => {
    const pinia = createPinia()
    const wrapper = mount(SettingsDrawer, {
      props: { modelValue: true },
      global: {
        plugins: [pinia, ElementPlus],
        stubs: { ElDrawer: { template: '<aside><slot /></aside>' } },
      },
    })
    const store = useRenameStore(pinia)
    const resultLimit = wrapper.findAllComponents({ name: 'ElInputNumber' })[0]

    expect(store.previewLimit).toBe(100)
    expect(wrapper.text()).toContain('结果显示')
    expect(wrapper.text()).toContain('全部')
    expect(resultLimit.props('min')).toBe(1)
    expect(resultLimit.props('max')).toBeGreaterThan(100)
  })
})
