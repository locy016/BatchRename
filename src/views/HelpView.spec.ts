import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AboutView from './AboutView.vue'
import UsageGuideView from './UsageGuideView.vue'

describe('帮助页面', () => {
  it('使用说明独立呈现完整操作流程和安全反馈', () => {
    const wrapper = mount(UsageGuideView, {
      global: { stubs: { ElAlert: true } },
    })

    expect(wrapper.get('h1').text()).toBe('使用说明')
    expect(wrapper.text()).toContain('快速开始')
    expect(wrapper.text()).toContain('正则模板')
    expect(wrapper.text()).toContain('键盘操作')
    expect(wrapper.text()).toContain('结果状态')
    expect(wrapper.text()).toContain('操作日志')
    expect(wrapper.text()).toContain('整批撤回')
  })

  it('关于页面独立呈现能力、版本、数据、安全和联系信息', () => {
    const wrapper = mount(AboutView)

    expect(wrapper.get('h1').text()).toBe('关于')
    expect(wrapper.text()).toContain('2.0.0 Alpha')
    expect(wrapper.text()).toContain('当前能力')
    expect(wrapper.text()).toContain('后续方向')
    expect(wrapper.text()).toContain('数据位置')
    expect(wrapper.text()).toContain('免责声明')
    expect(wrapper.text()).toContain('lo.c@live.cn')
  })
})
