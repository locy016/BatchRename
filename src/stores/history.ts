import { defineStore } from 'pinia'
import { desktopApi, type OperationSummary, type UndoCheck } from '../api/desktop'
import type { OperationLogV1 } from '../types/contracts'

export const useHistoryStore = defineStore('history', {
  state: () => ({
    items: [] as OperationSummary[],
    total: 0,
    selectedIdentifier: '',
    selected: null as OperationLogV1 | null,
    undoCheck: null as UndoCheck | null,
    loading: false,
    selectionBusy: false,
    undoBusy: false,
    errorMessage: '',
    undoError: '',
    lastQuery: '',
    lastStatus: null as string | null,
    selectionGeneration: 0,
  }),
  actions: {
    async load(query?: string, status?: string | null, offset = 0) {
      const effectiveQuery = query ?? this.lastQuery
      const effectiveStatus = status === undefined ? this.lastStatus : status
      this.loading = true
      this.errorMessage = ''
      this.lastQuery = effectiveQuery
      this.lastStatus = effectiveStatus
      try {
        const page = await desktopApi.queryOperations({
          query: effectiveQuery,
          status: effectiveStatus,
          offset,
          limit: 50,
        })
        this.items = page.items
        this.total = page.total
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : String(error)
      } finally {
        this.loading = false
      }
    },

    async select(identifier: string) {
      const generation = ++this.selectionGeneration
      this.selectedIdentifier = identifier
      this.selectionBusy = true
      this.undoCheck = null
      this.undoError = ''

      const [operationResult, undoResult] = await Promise.allSettled([
        desktopApi.getOperation(identifier),
        desktopApi.checkUndo(identifier),
      ])
      if (generation !== this.selectionGeneration || identifier !== this.selectedIdentifier) return

      if (operationResult.status === 'fulfilled') {
        this.selected = operationResult.value
      } else {
        this.selected = null
        this.errorMessage = operationResult.reason instanceof Error
          ? operationResult.reason.message
          : String(operationResult.reason)
      }

      if (undoResult.status === 'fulfilled') {
        this.undoCheck = undoResult.value
      } else {
        this.undoError = undoResult.reason instanceof Error
          ? undoResult.reason.message
          : String(undoResult.reason)
      }
      this.selectionBusy = false
    },

    async executeUndo(): Promise<boolean> {
      const identifier = this.selectedIdentifier
      const check = this.undoCheck
      if (!identifier || !check || check.state !== '可撤回') return false

      this.undoBusy = true
      this.undoError = ''
      try {
        await desktopApi.undo(identifier, check.token, () => {})
        await this.select(identifier)
        await this.load()
        return true
      } catch (error) {
        this.undoError = error instanceof Error ? error.message : String(error)
        return false
      } finally {
        this.undoBusy = false
      }
    },
  },
})
