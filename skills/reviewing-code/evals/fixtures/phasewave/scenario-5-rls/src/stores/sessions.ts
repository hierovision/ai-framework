import { defineStore } from 'pinia'
import { supabase } from '../supabase/client'
import type { Database } from '../../types/database.types'

type SharedRow = Database['public']['Tables']['shared_sessions']['Row']

export const useSessionsStore = defineStore('sessions', {
  state: () => ({ shares: [] as SharedRow[] }),
  actions: {
    // Share a focus session (read-only) with another user. The owner's
    // RLS policy allows the insert; the sharee's RLS policy grants SELECT.
    async shareSession(sessionId: string, shareeId: string) {
      const { data, error } = await supabase
        .from('shared_sessions')
        .insert({ session_id: sessionId, sharee_id: shareeId })
        .select()
        .single()
      if (error) throw error
      this.shares.push(data as SharedRow)
      return data as SharedRow
    },
  },
})