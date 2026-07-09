import { defineStore } from 'pinia'
import { queueSession } from '../lib/offline-queue'

export const useFocusTimerStore = defineStore('focus-timer', {
  state: () => ({ active: null as null | { session_id: string; started_at: string } }),
  actions: {
    async start(label: string) {
      const started_at = new Date().toISOString()
      const row = { user_id: '', started_at, label }
      // Route through the offline outbox instead of a direct insert.
      const entry = queueSession({ table: 'focus_sessions', op: 'insert', row })
      this.active = { session_id: entry.id, started_at }
    },
    async stop() {
      this.active = null
    },
  },
})