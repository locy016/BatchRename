import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'

import AppShell from './AppShell.vue'

const routes = [
  { path: '/rename', component: { template: '<div>重命名工作台</div>' } },
  { path: '/history', component: { template: '<div>操作日志</div>' } },
  { path: '/help/guide', component: { template: '<div>使用说明</div>' } },
  { path: '/help/about', component: { template: '<div>关于</div>' } },
]

describe('AppShell', () => {
  it('只保留不重复的主功能导航', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes })
    await router.push('/rename')
    await router.isReady()

    const wrapper = mount(AppShell, { global: { plugins: [createPinia(), router, ElementPlus] } })

    expect(wrapper.find('[data-testid="product-title"]').exists()).toBe(false)
    expect(wrapper.findAll('nav > a')[0].text()).toBe('文件名管理')
    expect(wrapper.findAll('nav > a').map((link) => link.attributes('href'))).toEqual([
      '/rename',
      '/history',
    ])
    expect(wrapper.text()).not.toContain('撤回管理')
    expect(wrapper.get('[data-testid="help-menu"]').text()).toContain('帮助')
    expect(wrapper.findAllComponents({ name: 'ElDropdownItem' }).map((item) => item.text())).toEqual([
      '使用说明',
      '关于',
    ])

    wrapper.findComponent({ name: 'ElDropdown' }).vm.$emit('command', '/help/about')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/help/about')
  })
})
