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
    const inspectDirectory = vi.spyOn(desktopApi, 'inspectDirectory')
      .mockResolvedValue({ directories: 3, files: 7 })
    const store = useRenameStore()

    await store.chooseRoot()

    expect(inspectDirectory).toHaveBeenCalledWith('D:/资料', null)
    expect((store as unknown as { overview: object }).overview).toEqual({ directories: 3, files: 7 })
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
    expect(store.summary.matched).toBe(2)
    expect(store.items).toEqual(matchedItems)
    expect((store as unknown as { overview: object }).overview).toEqual({ directories: 2, files: 3 })
  })
})
