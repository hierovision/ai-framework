import { defineStore } from 'pinia'
import { supabase } from '../supabase/client'

export const useFocusTimerStore = defineStore('focus-timer', {
  state: () => ({ active: null as null | { session_id: string; started_at: string } }),
  actions: {
    async start(label: string) {
      // Direct insert — replaced by the offline queue below.
      const row = { user_id: '', started_at: new Date().toISOString(), label }
      throw new Error('supabase client not available in this fixture stub')
    },
    async stop() {
      this.active = null
    },
  },
})