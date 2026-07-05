export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  public: {
    Tables: {
      activities: {
        Row: {
          id: string
          user_id: string
          name: string
          duration_seconds: number
          deleted_at: string | null
        }
        Insert: {
          id?: string
          user_id: string
          name: string
          duration_seconds?: number
          deleted_at?: string | null
        }
        Update: {
          id?: string
          user_id?: string
          name?: string
          duration_seconds?: number
          deleted_at?: string | null
        }
      }
      focus_sessions: {
        Row: {
          id: string
          user_id: string
          activity_id: string | null
          duration_seconds: number
          started_at: string
          ended_at: string | null
          status: string // running | completed | abandoned
        }
        Insert: {
          id?: string
          user_id: string
          activity_id?: string | null
          duration_seconds: number
          started_at: string
          ended_at?: string | null
          status?: string
        }
        Update: {
          id?: string
          user_id?: string
          activity_id?: string | null
          duration_seconds?: number
          started_at?: string
          ended_at?: string | null
          status?: string
        }
      }
    }
    Views: {}
    Functions: {}
  }
}

export type ActivityRow = Database['public']['Tables']['activities']['Row']
export type ActivityInsert = Database['public']['Tables']['activities']['Insert']
export type FocusSession = Database['public']['Tables']['focus_sessions']['Row']
export type FocusSessionInsert = Database['public']['Tables']['focus_sessions']['Insert']
export type FocusSessionUpdate = Database['public']['Tables']['focus_sessions']['Update']