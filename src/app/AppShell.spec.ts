import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'

import AppShell from './AppShell.vue'

const routes = [
  { path: '/rename', component: { template: '<div>重命名工作台</div>' } },
  { path: '/history', component: { template: '<div>操作日志</div>' } },
  { path: '/undo', component: { template: '<div>撤回管理</div>' } },
  { path: '/help/guide', component: { template: '<div>使用说明</div>' } },
  { path: '/help/about', component: { template: '<div>关于</div>' } },
]

describe('AppShell', () => {
  it('presents the product identity and every primary workspace route', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes })
    await router.push('/rename')
    await router.isReady()

    const wrapper = mount(AppShell, { global: { plugins: [createPinia(), router, ElementPlus] } })

    expect(wrapper.get('[data-testid="product-title"]').text()).toContain('批量重命名')
    expect(wrapper.findAll('nav > a').map((link) => link.attributes('href'))).toEqual([
      '/rename',
      '/history',
      '/undo',
    ])
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
