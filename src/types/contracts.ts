export type ItemKind = '文件夹' | '文件'

export type CandidateStatus =
  | '可修改'
  | '名称未变化'
  | '目标已存在'
  | '批内目标重复'
  | '名称不合法'
  | '无法处理'

export interface MatchOptions {
  root: string
  search: string
  useRegex: boolean
  maxDepth: number | null
  includeFiles: boolean
  includeDirs: boolean
}

export interface MatchedItem {
  source: string
  kind: ItemKind
}

export interface RenameCandidate {
  source: string
  target: string
  kind: ItemKind
  status: CandidateStatus
  detail: string
}

export type OperationStatus =
  | '准备中'
  | '执行中'
  | '已完成'
  | '部分失败'
  | '已中断'
  | '撤回检查失败'
  | '撤回中'
  | '已撤回'
  | '部分撤回'
  | '记录损坏'

export type UndoStatus = '待撤回' | '已撤回' | '撤回失败' | '无需撤回'

export interface OperationItemV1 {
  source: string
  target: string
  kind: ItemKind
  outcome: string
  detail: string
  execution_index: number | null
  undo_status: UndoStatus
  undo_detail: string
}

export interface OperationLogV1 {
  schema_version: 1
  identifier: string
  created_at: string
  updated_at: string
  root: string
  search: string
  replacement: string
  use_regex: boolean
  max_depth: number | null
  include_files: boolean
  include_dirs: boolean
  rename_extension: boolean
  status: OperationStatus
  items: OperationItemV1[]
  error: string
}
