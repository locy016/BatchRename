import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { useHistoryStore } from '../stores/history'
import { useUndoStore } from '../stores/undo'
import UndoView from './UndoView.vue'

describe('撤回管理', () => {
  it('没有可撤回检查结果时不能执行', () => {
    setActivePinia(createPinia())
    const store = useUndoStore()

    expect(store.check?.state === '可撤回').toBe(false)
  })

  it('撤回结束后刷新左侧日志状态', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const history = useHistoryStore()
    const undo = useUndoStore()
    const load = vi.spyOn(history, 'load').mockResolvedValue()
    const execute = vi.spyOn(undo, 'execute').mockResolvedValue()
    const wrapper = shallowMount(UndoView, {
      global: { plugins: [pinia] },
    })
    await flushPromises()

    wrapper.findComponent({ name: 'UndoCheckPanel' }).vm.$emit('execute')
    await flushPromises()

    expect(execute).toHaveBeenCalledOnce()
    expect(load).toHaveBeenCalledTimes(2)
  })
})
