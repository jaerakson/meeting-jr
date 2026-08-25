export type JobStatus =
  | 'pending'
  | 'converting'
  | 'diarizing'
  | 'transcribing'
  | 'awaiting_edit'
  | 'summarizing'
  | 'done'
  | 'error'

export interface Category {
  id: string
  name: string
  icon: string
  description: string
  prompt: string
  is_builtin: number
  sort_order: number
}

export interface ActionItem {
  text: string
  assignee: string
  done: boolean
}

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
  category_id?: string
  action_items?: ActionItem[]
  bookmarked?: number
  memo?: string
  tags?: string[]
}

export interface RelatedMeeting {
  id: string
  title: string
  created_at: string
  matched_keywords: string[]
  score: number
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
