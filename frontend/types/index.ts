export type JobStatus =
  | 'pending'
  | 'converting'
  | 'diarizing'
  | 'transcribing'
  | 'awaiting_edit'
  | 'summarizing'
  | 'done'
  | 'error'

export interface Job {
  id: string
  title: string
  filename: string
  status: JobStatus
  created_at: string
  duration_sec?: number
  transcript?: string
  summary?: string
  speakers?: Record<string, string>
  error_msg?: string
  notion_url?: string
  notion_page_id?: string
}

export interface ProgressEvent {
  stage: string
  progress: number
  message: string
  transcript?: string
  speakers?: string[]
  suggested_names?: Record<string, string>
}

export interface SettingsStatus {
  HF_TOKEN: { set: boolean; preview: string | null }
  NOTION_API_KEY: { set: boolean; preview: string | null }
  NOTION_DATABASE_ID: { set: boolean; preview: string | null }
}

export interface ClaudeStatus {
  installed: boolean
  logged_in: boolean
  email?: string
  auth_method?: string
  subscription_type?: string
}
