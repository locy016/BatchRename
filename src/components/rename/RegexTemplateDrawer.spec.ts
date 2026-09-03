import { createPinia } from 'pinia'
import { shallowMount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import RegexTemplateDrawer from './RegexTemplateDrawer.vue'

describe('正则模板抽屉', () => {
  it('使用明确像素宽度避免抽屉在宽屏中溢出', () => {
    const wrapper = shallowMount(RegexTemplateDrawer, {
      props: { modelValue: true },
      global: { plugins: [createPinia(), ElementPlus] },
    })

    expect(wrapper.findComponent({ name: 'ElDrawer' }).props('size')).toBe(460)
  })
})
