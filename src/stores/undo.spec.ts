import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { desktopApi, type UndoCheck } from '../api/desktop'
import { useUndoStore } from './undo'

vi.mock('../api/desktop', () => ({
  desktopApi: {
    checkUndo: vi.fn(),
    undo: vi.fn(),
  },
}))

const readyCheck: UndoCheck = {
  operationId: 'operation-1',
  token: 'token-1',
  state: '可撤回',
  summary: '检查通过，可撤回 1 项。',
  items: [{
    itemIndex: 0,
    currentSource: '新名称.txt',
    restoreTarget: '原名称.txt',
    kind: '文件',
    safe: true,
    detail: '可以恢复原名称。',
  }],
}

describe('撤回状态仓库', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('仅按明确的可撤回状态执行并重新读取结果', async () => {
    const completedCheck: UndoCheck = {
      ...readyCheck,
      state: '已撤回',
      summary: '这次操作已全部撤回，原名称已经恢复。',
      items: [],
    }
    vi.mocked(desktopApi.undo).mockResolvedValue({ succeeded: 1, failed: 0 })
    vi.mocked(desktopApi.checkUndo).mockResolvedValue(completedCheck)
    const store = useUndoStore()
    store.identifier = 'operation-1'
    store.check = readyCheck

    await store.execute()

    expect(desktopApi.undo).toHaveBeenCalledWith('operation-1', 'token-1', expect.any(Function))
    expect(desktopApi.checkUndo).toHaveBeenCalledWith('operation-1')
    expect(store.check?.state).toBe('已撤回')
    expect(store.busy).toBe(false)
  })

  it('检查失败后恢复可操作状态', async () => {
    vi.mocked(desktopApi.checkUndo).mockRejectedValue(new Error('读取失败'))
    const store = useUndoStore()

    await expect(store.inspect('operation-1')).rejects.toThrow('读取失败')

    expect(store.busy).toBe(false)
  })
})
