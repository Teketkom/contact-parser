// TypeScript interfaces matching backend Pydantic models

export type TaskMode = number

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

// ── New types for redesign ─────────────────────────────────────────────────

export interface DashboardStats {
  total_tasks: number
  total_contacts: number
  total_sites_processed: number
  avg_speed: number
  contacts_by_day: { date: string; count: number }[]
  recent_tasks: TaskResponse[]
}

export interface LLMStatus {
  model_name: string
  tokens_used_today: number
  avg_response_time: number
  is_connected: boolean
}

export interface SystemStatus {
  backend_healthy: boolean
  llm_connected: boolean
  disk_usage_percent: number
  uptime_seconds: number
  version: string
}

export interface AIChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

export interface AIChatRequest {
  message: string
  system_prompt?: string
}

export interface AIChatResponse {
  message: string
  tokens_used: number
}

export interface BlacklistEntry {
  id: string
  value: string
  type: 'domain' | 'email' | 'inn'
  added_at: string
}

export interface BlacklistData {
  domains: number
  emails: number
  inns: number
  total: number
  entries?: BlacklistEntry[]
}

export interface AppSettings {
  llm_model: string
  llm_api_url: string
  llm_api_key: string
  llm_timeout: number
  max_pages_per_site: number
  concurrent_browsers: number
  request_delay: number
}
