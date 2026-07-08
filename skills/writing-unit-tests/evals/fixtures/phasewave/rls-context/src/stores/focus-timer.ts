import { defineStore } from 'pinia'
import { supabase } from '@/supabase/client'
import type { FocusSession, FocusSessionInsert } from '@/types/database.types'

export const useFocusTimerStore = defineStore('focusTimer', {
  state: () => ({
    current: null as FocusSession | null,
    running: false,
    remainingSeconds: 0,
    sessions: [] as FocusSession[],
  }),
  actions: {
    async start(activityId: string, durationSeconds: number) {
      const insert: FocusSessionInsert = {
        activity_id: activityId,
        duration_seconds: durationSeconds,
        started_at: new Date().toISOString(),
        status: 'running',
      }
      const { data, error } = await supabase.from('focus_sessions').insert(insert).select().single()
      if (error) throw error
      this.current = data
      this.running = true
      this.remainingSeconds = durationSeconds
    },
    async loadSessions() {
      const { data, error } = await supabase.from('focus_sessions').select('*').order('started_at', { ascending: false })
      if (error) throw error
      this.sessions = data
    },
  },
})
