import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { desktopApi, type UndoCheck } from '../api/desktop'
import { useHistoryStore } from '../stores/history'
import type { OperationLogV1 } from '../types/contracts'

const operation: OperationLogV1 = {
  schema_version: 1,
  identifier: 'operation-1',
  created_at: '2026-09-03T10:00:00+08:00',
  updated_at: '2026-09-03T10:00:00+08:00',
  root: 'D:/资料',
  search: '旧版',
  replacement: '正式',
  use_regex: false,
  max_depth: null,
  include_files: true,
  include_dirs: true,
  rename_extension: false,
  status: '已完成',
  items: [{
    source: 'D:/资料/旧版.txt',
    target: 'D:/资料/正式.txt',
    kind: '文件',
    outcome: '成功',
    detail: '重命名完成',
    execution_index: 1,
    undo_status: '待撤回',
    undo_detail: '',
  }],
  error: '',
}

const readyCheck: UndoCheck = {
  operationId: 'operation-1',
  token: 'token-1',
  state: '可撤回',
  summary: '检查通过，可撤回 1 项。',
  items: [{
    itemIndex: 0,
    currentSource: 'D:/资料/正式.txt',
    restoreTarget: 'D:/资料/旧版.txt',
    kind: '文件',
    safe: true,
    detail: '可以恢复原名称。',
  }],
}

describe('操作日志统一状态', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('初始列表为空且详情延迟加载', () => {
    const store = useHistoryStore()
    expect(store.items).toEqual([])
    expect(store.selected).toBeNull()
  })

  it('筛选范围覆盖日志模型的全部状态', async () => {
    const source = await import('../components/history/OperationFilters.vue?raw')
    for (const status of ['准备中', '执行中', '撤回检查失败', '撤回中']) {
      expect(source.default).toContain(status)
    }
  })

  it('选择日志时同时读取详情和撤回安全状态', async () => {
    vi.spyOn(desktopApi, 'getOperation').mockResolvedValue(operation)
    vi.spyOn(desktopApi, 'checkUndo').mockResolvedValue(readyCheck)
    const store = useHistoryStore()

    await store.select('operation-1')

    expect(desktopApi.getOperation).toHaveBeenCalledWith('operation-1')
    expect(desktopApi.checkUndo).toHaveBeenCalledWith('operation-1')
    expect(store.selected).toEqual(operation)
    expect(store.undoCheck).toEqual(readyCheck)
    expect(store.selectionBusy).toBe(false)
  })

  it('撤回完成后刷新详情、检查状态和当前日志列表', async () => {
    const completedOperation = { ...operation, status: '已撤回' as const }
    const completedCheck = {
      ...readyCheck,
      state: '已撤回' as const,
      summary: '原名称已经恢复。',
      items: [],
    }
    vi.spyOn(desktopApi, 'undo').mockResolvedValue({ succeeded: 1, failed: 0 })
    vi.spyOn(desktopApi, 'getOperation').mockResolvedValue(completedOperation)
    vi.spyOn(desktopApi, 'checkUndo').mockResolvedValue(completedCheck)
    vi.spyOn(desktopApi, 'queryOperations').mockResolvedValue({ items: [], total: 0 })
    const store = useHistoryStore()
    store.selectedIdentifier = 'operation-1'
    store.undoCheck = readyCheck
    store.lastQuery = '旧版'
    store.lastStatus = '已完成'

    const completed = await store.executeUndo()

    expect(completed).toBe(true)
    expect(desktopApi.undo).toHaveBeenCalledWith('operation-1', 'token-1', expect.any(Function))
    expect(desktopApi.queryOperations).toHaveBeenCalledWith({
      query: '旧版', status: '已完成', offset: 0, limit: 50,
    })
    expect(store.selected?.status).toBe('已撤回')
    expect(store.undoCheck?.state).toBe('已撤回')
    expect(store.undoBusy).toBe(false)
  })

  it('撤回期间保留逐项进度并记录最终结果', async () => {
    vi.spyOn(desktopApi, 'undo').mockImplementation(async (_identifier, _token, progress) => {
      progress({
        current: 2,
        total: 3,
        path: 'D:/资料/旧版/报告.txt',
        outcome: '成功',
        detail: '已恢复原名称',
      })
      return { succeeded: 2, failed: 1 }
    })
    vi.spyOn(desktopApi, 'getOperation').mockResolvedValue({ ...operation, status: '部分撤回' })
    vi.spyOn(desktopApi, 'checkUndo').mockResolvedValue({
      ...readyCheck,
      state: '存在风险',
      summary: '仍有 1 项需要处理。',
    })
    vi.spyOn(desktopApi, 'queryOperations').mockResolvedValue({ items: [], total: 0 })
    const store = useHistoryStore()
    store.selectedIdentifier = 'operation-1'
    store.undoCheck = readyCheck

    expect(await store.executeUndo()).toBe(true)
    expect(store.undoProgress).toEqual({
      current: 2,
      total: 3,
      path: 'D:/资料/旧版/报告.txt',
      outcome: '成功',
      detail: '已恢复原名称',
    })
    expect(store.undoSummary).toEqual({ succeeded: 2, failed: 1 })
  })
})
