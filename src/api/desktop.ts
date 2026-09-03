import { Channel, invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'
import type { MatchOptions, MatchedItem, OperationLogV1, RenameCandidate } from '../types/contracts'

export interface PreviewSummary {
  matched: number
  ready: number
  unchanged: number
  conflicts: number
  invalid: number
}

export interface DirectoryOverview {
  directories: number
  files: number
  warnings?: string[]
}

export interface ScanProgress {
  jobId: string
  phase: string
  scannedTotal: number
  scannedDirectoryCount: number
  scannedFileCount: number
  matchedTotal: number
  warning?: string
}

export interface MatchPage {
  items: MatchedItem[]
  total: number
  offset: number
  limit: number
}

export interface ScanResult {
  jobId: string
  overview: DirectoryOverview
  page: MatchPage
  warnings: string[]
}

export interface PreviewPage {
  items: RenameCandidate[]
  total: number
  offset: number
  limit: number
  summary: PreviewSummary
  warnings: string[]
}

export interface OperationSummary {
  identifier: string
  createdAt: string
  updatedAt: string
  root: string
  search: string
  replacement: string
  status: string
  itemCount: number
  successCount: number
  failedCount: number
}

export interface OperationPage { items: OperationSummary[]; total: number }

export type UndoCheckState = '可撤回' | '存在风险' | '已撤回' | '不可用'

export interface UndoCheck {
  operationId: string
  token: string
  state: UndoCheckState
  summary: string
  items: Array<{
    itemIndex: number
    currentSource: string
    restoreTarget: string
    kind: string
    safe: boolean
    detail: string
  }>
}

export interface DesktopApi {
  chooseDirectory(): Promise<string | null>
  inspectDirectory(root: string, maxDepth: number | null): Promise<DirectoryOverview>
  listRootItems(root: string, limit: number): Promise<MatchPage>
  startScan(options: MatchOptions, onProgress: (event: ScanProgress) => void): Promise<ScanResult>
  cancelActiveJob(): Promise<void>
  buildPreview(jobId: string, replacement: string, renameExtension: boolean): Promise<PreviewPage>
  getPreviewPage(jobId: string, offset: number, limit: number): Promise<PreviewPage>
  execute(jobId: string, options: object, onProgress: (event: object) => void): Promise<{ operationId: string; succeeded: number; skipped: number; failed: number }>
  queryOperations(query: object): Promise<OperationPage>
  getOperation(identifier: string): Promise<OperationLogV1>
  checkUndo(identifier: string): Promise<UndoCheck>
  undo(identifier: string, token: string, onProgress: (event: object) => void): Promise<{ succeeded: number; failed: number }>
  loadPreferences(): Promise<{ appearance: string }>
  savePreferences(appearance: string): Promise<void>
}

const inDesktop = () => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

function events<T>(handler: (event: T) => void) {
  const channel = new Channel<T>()
  channel.onmessage = handler
  return channel
}

function desktopOnly<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  return inDesktop()
    ? invoke<T>(command, args)
    : Promise.reject(new Error('当前为浏览器预览环境'))
}

export const desktopApi: DesktopApi = {
  async chooseDirectory() {
    if (!inDesktop()) return null
    const value = await open({ directory: true, multiple: false })
    return typeof value === 'string' ? value : null
  },
  inspectDirectory: (root, maxDepth) => desktopOnly('inspect_directory', { root, maxDepth }),
  listRootItems: (root, limit) => desktopOnly('list_root_items', { root, limit }),
  startScan: (options, handler) => desktopOnly('start_scan', { options, events: events(handler) }),
  cancelActiveJob: () => desktopOnly('cancel_active_job'),
  buildPreview: (jobId, replacement, renameExtension) => desktopOnly('build_rename_preview', { jobId, replacement, renameExtension }),
  getPreviewPage: (jobId, offset, limit) => desktopOnly('get_preview_page', { jobId, offset, limit }),
  execute: (jobId, options, handler) => desktopOnly('execute_rename', { jobId, options, events: events(handler) }),
  queryOperations: (query) => inDesktop() ? invoke('query_operations', { query }) : Promise.resolve({ items: [], total: 0 }),
  getOperation: (identifier) => desktopOnly('get_operation', { identifier }),
  checkUndo: (identifier) => desktopOnly('check_undo', { identifier }),
  undo: (identifier, token, handler) => desktopOnly('undo_operation', { identifier, token, events: events(handler) }),
  loadPreferences: () => inDesktop() ? invoke('load_preferences') : Promise.resolve({ appearance: 'system' }),
  savePreferences: (appearance) => inDesktop() ? invoke('save_preferences', { appearance }) : Promise.resolve(),
}
