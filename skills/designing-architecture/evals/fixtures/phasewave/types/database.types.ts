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