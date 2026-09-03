import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { desktopApi } from '../api/desktop'
import { useRenameStore } from './rename'

describe('工作流状态', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('匹配条件变化使扫描失效', () => {
    const store = useRenameStore()
    store.scanJobId = 'a'
    store.setSearch('新')
    expect(store.scanJobId).toBeNull()
  })

  it('替换变化只使预览失效', () => {
    const store = useRenameStore()
    store.scanJobId = 'a'
    store.previewValid = true
    store.setReplacement('新')
    expect(store.scanJobId).toBe('a')
    expect(store.previewValid).toBe(false)
  })

  it('扫描期间修改条件会取消旧任务并忽略其迟到结果', async () => {
    let finishScan!: (value: unknown) => void
    vi.spyOn(desktopApi, 'startScan').mockReturnValue(new Promise((resolve) => {
      finishScan = resolve
    }) as never)
    const cancel = vi.spyOn(desktopApi, 'cancelActiveJob').mockResolvedValue()
    const store = useRenameStore()
    store.root = 'D:/资料'
    store.search = '旧'
    const pending = store.scan()
    await Promise.resolve()

    store.setSearch('新')
    finishScan({
      jobId: 'old-job', overview: { directories: 4, files: 5 },
      page: { items: [], total: 9, offset: 0, limit: 100 }, warnings: [],
    })
    await pending

    expect(cancel).toHaveBeenCalledOnce()
    expect(store.busy).toBe('')
    expect(store.scanJobId).toBeNull()
    expect(store.summary.matched).toBe(0)
  })

  it('目录选定后立即读取文件夹和文件数量', async () => {
    vi.spyOn(desktopApi, 'chooseDirectory').mockResolvedValue('D:/资料')
    const listRootItems = vi.spyOn(desktopApi, 'listRootItems').mockResolvedValue({
      items: [
        { source: 'D:/资料/项目目录', kind: '文件夹' },
        { source: 'D:/资料/说明.txt', kind: '文件' },
      ],
      total: 2,
      offset: 0,
      limit: 100,
    })
    const inspectDirectory = vi.spyOn(desktopApi, 'inspectDirectory')
      .mockResolvedValue({ directories: 3, files: 7 })
    const store = useRenameStore()

    await store.chooseRoot()

    expect(listRootItems).toHaveBeenCalledWith('D:/资料', 100)
    expect(inspectDirectory).toHaveBeenCalledWith('D:/资料', null)
    expect((store as unknown as { overview: object }).overview).toEqual({ directories: 3, files: 7 })
    expect(store.resultMode).toBe('directory')
    expect(store.items.map((item) => item.source)).toEqual([
      'D:/资料/项目目录',
      'D:/资料/说明.txt',
    ])
  })

  it('输入查找内容前保留根目录列表，扫描后切换为匹配结果', async () => {
    vi.spyOn(desktopApi, 'startScan').mockResolvedValue({
      jobId: 'scan-job',
      overview: { directories: 1, files: 1 },
      page: {
        items: [{ source: 'D:/资料/匹配.txt', kind: '文件' }],
        total: 1,
        offset: 0,
        limit: 100,
      },
      warnings: [],
    })
    const store = useRenameStore()
    store.root = 'D:/资料'
    store.resultMode = 'directory'
    store.rootItems = [{ source: 'D:/资料/说明.txt', kind: '文件' }]
    store.items = [{
      source: 'D:/资料/说明.txt',
      target: 'D:/资料/说明.txt',
      kind: '文件',
      status: '目录项目',
      detail: '根目录内容',
    }]

    store.setSearch('匹配')

    expect(store.resultMode).toBe('directory')
    expect(store.items[0].source).toBe('D:/资料/说明.txt')

    await store.scan()

    expect(store.resultMode).toBe('matches')
    expect(store.items[0].source).toBe('D:/资料/匹配.txt')
  })

  it('显示上限只裁剪表格且规则变化不缩小完整匹配统计', async () => {
    const matched = Array.from({ length: 100 }, (_, index) => ({
      source: `D:/资料/项目${index + 1}.txt`,
      kind: '文件' as const,
    }))
    vi.spyOn(desktopApi, 'startScan').mockResolvedValue({
      jobId: 'scan-many',
      overview: { directories: 0, files: 150 },
      page: { items: matched, total: 150, offset: 0, limit: 100 },
      warnings: [],
    })
    const store = useRenameStore()
    store.root = 'D:/资料'
    store.search = '项目'
    store.setPreviewLimit(25)

    await store.scan()
    expect(store.items).toHaveLength(25)
    expect(store.summary.matched).toBe(150)

    store.setReplacement('新版')
    expect(store.items).toHaveLength(25)
    expect(store.summary.matched).toBe(150)
  })

  it('扫描结果为空时仍保持匹配结果语义', async () => {
    vi.spyOn(desktopApi, 'startScan').mockResolvedValue({
      jobId: 'empty-scan',
      overview: { directories: 1, files: 1 },
      page: { items: [], total: 0, offset: 0, limit: 100 },
      warnings: [],
    })
    const store = useRenameStore()
    store.root = 'D:/资料'
    store.search = '不存在'
    store.rootItems = [{ source: 'D:/资料/说明.txt', kind: '文件' }]

    await store.scan()
    store.setReplacement('新名称')

    expect(store.resultMode).toBe('matches')
    expect(store.items).toEqual([])
  })

  it('快速完成的扫描不会因任务编号返回较晚而丢失结果', async () => {
    vi.spyOn(desktopApi, 'startScan').mockImplementation(async (_options, onProgress) => {
      onProgress({
        jobId: 'fast-job',
        phase: '完成',
        scannedTotal: 5,
        matchedTotal: 2,
        scannedDirectoryCount: 2,
        scannedFileCount: 3,
      } as never)
      return {
        jobId: 'fast-job',
        overview: { directories: 2, files: 3 },
        page: {
          items: [
            { source: 'D:/资料/项目目录', kind: '文件夹' },
            { source: 'D:/资料/项目.txt', kind: '文件' },
          ],
          total: 2,
          offset: 0,
          limit: 100,
        },
        warnings: [],
      } as never
    })
    const matchedItems = [
      { source: 'D:/资料/项目目录', target: 'D:/资料/项目目录', kind: '文件夹', status: '已匹配', detail: '名称符合当前查找规则；填写替换内容后可生成重命名预览。' },
      { source: 'D:/资料/项目.txt', target: 'D:/资料/项目.txt', kind: '文件', status: '已匹配', detail: '名称符合当前查找规则；填写替换内容后可生成重命名预览。' },
    ]
    const store = useRenameStore()
    store.root = 'D:/资料'
    store.search = '项目'

    await store.scan()

    expect(store.busy).toBe('')
    expect(store.resultMode).toBe('matches')
    expect(store.summary.matched).toBe(2)
    expect(store.items).toEqual(matchedItems)
    expect((store as unknown as { overview: object }).overview).toEqual({ directories: 2, files: 3 })
  })

  it('执行期间接收逐项进度并在成功后恢复可操作状态', async () => {
    vi.spyOn(desktopApi, 'execute').mockImplementation(async (_jobId, _options, onProgress) => {
      onProgress({
        current: 1,
        total: 2,
        relativePath: '子目录/旧名称.txt',
        outcome: '成功',
        detail: '已完成重命名',
      })
      return { operationId: 'operation-1', succeeded: 2, skipped: 0, failed: 0 }
    })
    const store = useRenameStore()
    store.scanJobId = 'scan-job'

    const succeeded = await store.execute()

    expect(succeeded).toBe(true)
    expect(store.executionProgress).toEqual({
      current: 1,
      total: 2,
      relativePath: '子目录/旧名称.txt',
      outcome: '成功',
      detail: '已完成重命名',
    })
    expect(store.lastOperationId).toBe('operation-1')
    expect(store.busy).toBe('')
  })

  it('执行失败时关闭阻断状态并保留可读错误', async () => {
    vi.spyOn(desktopApi, 'execute').mockRejectedValue(new Error('目标文件被占用'))
    const store = useRenameStore()
    store.scanJobId = 'scan-job'

    const succeeded = await store.execute()

    expect(succeeded).toBe(false)
    expect(store.busy).toBe('')
    expect(store.errorMessage).toBe('目标文件被占用')
  })
})
