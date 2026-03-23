// TypeScript interfaces matching backend Pydantic models

export type TaskMode = 1 | 2 | 3

export type TaskStatus =
  | 'pending'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type ExtractionVariant = 'A' | 'B'

export interface TaskProgress {
  total_sites: number
  processed_sites: number
  total_pages: number
  contacts_found: number
  errors: number
  current_site?: string
  current_page?: string
  percent: number
  elapsed_seconds: number
  eta_seconds?: number
  llm_tokens_used: number
  fallback_count: number
}

export interface TaskResponse {
  task_id: string
  status: TaskStatus
  mode: TaskMode
  variant: ExtractionVariant
  created_at: string
  started_at?: string
  finished_at?: string
  progress: TaskProgress
  result_file?: string
  log_file?: string
  error_message?: string
}

export interface ContactRecord {
  company_name?: string
  site_url?: string
  inn?: string
  kpp?: string
  company_email?: string
  position_raw?: string
  position_normalized?: string
  full_name?: string
  personal_email?: string
  phone?: string
  phone_raw?: string
  source_url?: string
  page_language?: string
  scan_date?: string
  status?: string
  comment?: string
  extraction_variant?: ExtractionVariant
}

export interface BlacklistUploadResponse {
  added: number
  total: number
  message: string
}

export interface ApiError {
  detail: string
  error?: string
}

export interface UploadFileInfo {
  filename: string
  size_bytes: number
  rows_count: number
  preview_urls: string[]
}

export interface WSMessage {
  type: 'progress' | 'log' | 'completed' | 'error' | 'cancelled'
  task_id: string
  data: Record<string, unknown>
  timestamp?: string
}
