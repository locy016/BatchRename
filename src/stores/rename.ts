import { defineStore } from 'pinia'
import {
  desktopApi,
  type DirectoryOverview,
  type ExecutionProgress,
  type PreviewSummary,
  type ScanProgress,
} from '../api/desktop'
import type { CandidateStatus, ItemKind, MatchedItem } from '../types/contracts'

export interface DisplayItem {
  source: string
  target: string
  kind: ItemKind
  status: CandidateStatus | '目录项目' | '已匹配'
  detail: string
}

export type ResultMode = 'empty' | 'directory' | 'matches' | 'preview'

const emptySummary = (): PreviewSummary => ({ matched: 0, ready: 0, unchanged: 0, conflicts: 0, invalid: 0 })
const emptyOverview = (): DirectoryOverview => ({ directories: 0, files: 0 })
const emptyExecutionProgress = (): ExecutionProgress => ({
  current: 0,
  total: 0,
  relativePath: '',
  outcome: '',
  detail: '',
})
const displayMatches = (items: MatchedItem[]): DisplayItem[] => items.map((item) => ({
  ...item,
  target: item.source,
  status: '已匹配',
  detail: '名称符合当前查找规则；填写替换内容后可生成重命名预览。',
}))
const displayRootItems = (items: MatchedItem[]): DisplayItem[] => items.map((item) => ({
  ...item,
  target: item.source,
  status: '目录项目',
  detail: '根目录中的项目；输入查找内容并扫描后可筛选符合项。',
}))

export const useRenameStore = defineStore('rename', {
  state: () => ({
    root: '',
    search: '',
    replacement: '',
    useRegex: false,
    maxDepth: null as number | null,
    includeFiles: true,
    includeDirs: true,
    renameExtension: false,
    scanJobId: null as string | null,
    scanGeneration: 0,
    overviewGeneration: 0,
    rootListingGeneration: 0,
    previewValid: false,
    resultMode: 'empty' as ResultMode,
    rootItems: [] as MatchedItem[],
    rootTotal: 0,
    matchedItems: [] as MatchedItem[],
    items: [] as DisplayItem[],
    summary: emptySummary(),
    overview: emptyOverview(),
    overviewBusy: false,
    warnings: [] as string[],
    errorMessage: '',
    busy: '' as '' | 'scanning' | 'previewing' | 'executing',
    progress: {
      jobId: '', phase: '', scannedTotal: 0, scannedDirectoryCount: 0,
      scannedFileCount: 0, matchedTotal: 0,
    } as ScanProgress,
    lastOperationId: '',
    executionProgress: emptyExecutionProgress(),
  }),
  getters: {
    canScan: (state) => !!state.root && !!state.search && !state.busy,
    canPreview: (state) => !!state.scanJobId && !state.busy,
    canExecute: (state) => state.previewValid && state.summary.ready > 0 && !state.busy,
  },
  actions: {
    invalidateScan() {
      if (this.busy === 'scanning') {
        this.busy = ''
        void desktopApi.cancelActiveJob().catch(() => undefined)
      }
      this.scanGeneration += 1
      this.scanJobId = null
      this.previewValid = false
      this.matchedItems = []
      if (this.rootItems.length || this.rootTotal > 0) {
        this.resultMode = 'directory'
        this.items = displayRootItems(this.rootItems)
      } else {
        this.resultMode = 'empty'
        this.items = []
      }
      this.summary = emptySummary()
      this.errorMessage = ''
    },
    invalidatePreview() {
      this.previewValid = false
      if (this.scanJobId) {
        this.items = displayMatches(this.matchedItems)
        this.resultMode = 'matches'
      } else {
        this.items = displayRootItems(this.rootItems)
        this.resultMode = this.root ? 'directory' : 'empty'
      }
      this.summary = { ...emptySummary(), matched: this.matchedItems.length }
    },
    setRoot(value: string) {
      if (this.root !== value) {
        this.root = value
        this.overview = emptyOverview()
        this.rootListingGeneration += 1
        this.rootItems = []
        this.rootTotal = 0
        this.invalidateScan()
      }
    },
    setSearch(value: string) {
      if (this.search !== value) {
        this.search = value
        this.invalidateScan()
      }
    },
    setReplacement(value: string) {
      if (this.replacement !== value) {
        this.replacement = value
        this.invalidatePreview()
      }
    },
    setMaxDepth(value: number | null) {
      const normalized = value === 0 ? null : value
      if (this.maxDepth !== normalized) {
        this.maxDepth = normalized
        this.invalidateScan()
        if (this.root) void this.refreshOverview()
      }
    },
    async refreshOverview() {
      if (!this.root) return
      const generation = ++this.overviewGeneration
      const root = this.root
      const depth = this.maxDepth
      this.overviewBusy = true
      try {
        const overview = await desktopApi.inspectDirectory(root, depth)
        if (generation !== this.overviewGeneration || root !== this.root) return
        this.overview = { directories: overview.directories, files: overview.files }
        if (overview.warnings?.length) this.warnings = overview.warnings
      } catch (error) {
        if (generation === this.overviewGeneration) {
          this.errorMessage = error instanceof Error ? error.message : String(error)
        }
      } finally {
        if (generation === this.overviewGeneration) this.overviewBusy = false
      }
    },
    async refreshRootItems() {
      if (!this.root) return
      const generation = ++this.rootListingGeneration
      const root = this.root
      try {
        const page = await desktopApi.listRootItems(root, 100)
        if (generation !== this.rootListingGeneration || root !== this.root) return
        this.rootItems = page.items
        this.rootTotal = page.total
        this.items = displayRootItems(page.items)
        this.resultMode = 'directory'
      } catch (error) {
        if (generation === this.rootListingGeneration) {
          this.errorMessage = error instanceof Error ? error.message : String(error)
        }
      }
    },
    async chooseRoot() {
      const value = await desktopApi.chooseDirectory()
      if (!value) return
      this.setRoot(value)
      await Promise.all([this.refreshRootItems(), this.refreshOverview()])
    },
    async scan() {
      if (!this.canScan) return
      const generation = ++this.scanGeneration
      this.busy = 'scanning'
      this.errorMessage = ''
      this.previewValid = false
      this.matchedItems = []
      this.summary = emptySummary()
      this.progress = {
        jobId: '', phase: '扫描', scannedTotal: 0,
        scannedDirectoryCount: 0, scannedFileCount: 0, matchedTotal: 0,
      }
      try {
        const result = await desktopApi.startScan({
          root: this.root,
          search: this.search,
          useRegex: this.useRegex,
          maxDepth: this.maxDepth,
          includeFiles: this.includeFiles,
          includeDirs: this.includeDirs,
        }, (event) => {
          if (generation !== this.scanGeneration) return
          this.progress = event
          this.overview = {
            directories: event.scannedDirectoryCount,
            files: event.scannedFileCount,
          }
          this.summary.matched = event.matchedTotal
        })
        if (generation !== this.scanGeneration) return
        this.scanJobId = result.jobId
        this.overview = {
          directories: result.overview.directories,
          files: result.overview.files,
        }
        this.matchedItems = result.page.items
        this.items = displayMatches(result.page.items)
        this.resultMode = 'matches'
        this.summary = { ...emptySummary(), matched: result.page.total }
        this.warnings = result.warnings
        this.progress = {
          jobId: result.jobId,
          phase: '完成',
          scannedTotal: result.overview.directories + result.overview.files,
          scannedDirectoryCount: result.overview.directories,
          scannedFileCount: result.overview.files,
          matchedTotal: result.page.total,
        }
      } catch (error) {
        if (generation !== this.scanGeneration) return
        this.errorMessage = error instanceof Error ? error.message : String(error)
      } finally {
        if (generation === this.scanGeneration) this.busy = ''
      }
    },
    async preview() {
      if (!this.scanJobId) return
      this.busy = 'previewing'
      this.errorMessage = ''
      try {
        const page = await desktopApi.buildPreview(this.scanJobId, this.replacement, this.renameExtension)
        this.items = page.items
        this.resultMode = 'preview'
        this.summary = page.summary
        this.warnings = page.warnings
        this.previewValid = true
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : String(error)
      } finally {
        this.busy = ''
      }
    },
    async execute(): Promise<boolean> {
      if (!this.scanJobId) return false
      this.busy = 'executing'
      this.errorMessage = ''
      this.executionProgress = emptyExecutionProgress()
      try {
        const result = await desktopApi.execute(this.scanJobId, {
          search: this.search,
          replacement: this.replacement,
          useRegex: this.useRegex,
          maxDepth: this.maxDepth,
          includeFiles: this.includeFiles,
          includeDirs: this.includeDirs,
          renameExtension: this.renameExtension,
        }, (event) => {
          this.executionProgress = event
        })
        this.lastOperationId = result.operationId
        return true
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : String(error)
        return false
      } finally {
        this.busy = ''
      }
    },
  },
})
