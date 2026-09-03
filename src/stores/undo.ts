import { defineStore } from 'pinia'
import { desktopApi, type UndoCheck } from '../api/desktop'

export const useUndoStore = defineStore('undo', {
  state: () => ({
    identifier: '',
    check: null as UndoCheck | null,
    busy: false,
  }),
  actions: {
    async inspect(identifier: string) {
      this.identifier = identifier
      this.busy = true
      try {
        this.check = await desktopApi.checkUndo(identifier)
      } finally {
        this.busy = false
      }
    },
    async execute() {
      const check = this.check
      const identifier = this.identifier
      if (!check || check.state !== '可撤回') return

      this.busy = true
      try {
        await desktopApi.undo(identifier, check.token, () => {})
        this.check = await desktopApi.checkUndo(identifier)
      } finally {
        this.busy = false
      }
    },
  },
})
