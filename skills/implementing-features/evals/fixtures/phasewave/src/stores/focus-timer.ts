import { defineStore } from 'pinia'
import { supabase } from '@/supabase/client'
import type { FocusSession, FocusSessionInsert } from '@/types/database.types'

export const useFocusTimerStore = defineStore('focusTimer', {
  state: () => ({
    current: null as FocusSession | null,
    running: false,
    remainingSeconds: 0,
  }),
  actions: {
    async start(activityId: string, durationSeconds: number) {
      const insert: FocusSessionInsert = {
        activity_id: activityId,
        duration_seconds: durationSeconds,
        started_at: new Date().toISOString(),
        status: 'running',
      }
      // Direct write — offline will fail silently today (the bug
      // feat-offline-queue addresses: route this insert through the
      // offline queue so it survives connectivity loss).
      const { data, error } = await supabase.from('focus_sessions').insert(insert).select().single()
      if (error) throw error
      this.current = data
      this.running = true
      this.remainingSeconds = durationSeconds
    },
    async complete() {
      if (!this.current) return
      const { error } = await supabase
        .from('focus_sessions')
        .update({ status: 'completed', ended_at: new Date().toISOString() })
        .eq('id', this.current.id)
      if (error) throw error
      this.running = false
      this.current = null
    },
  },
})