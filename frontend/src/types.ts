// TypeScript interfaces matching backend Pydantic models

export type TaskMode = 1 | 2

export type TaskStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface ContactRecord {
  id?: number
  task_id: string
  site_url: string
  company_name?: string
  full_name?: string
  position?: string
  email?: string
  phone?: string
  inn?: string
  kpp?: string
  source_url?: string
  matched_positions?: string[]
  raw_text?: string
  created_at?: string
}

export interface TaskProgress {
  task_id: string
  status: TaskStatus
  total_sites: number
  processed_sites: number
  found_records: number
  error_count: number
  current_site?: string
  current_site_index?: number
  elapsed_seconds: number
  estimated_remaining_seconds?: number
  errors: string[]
  message?: string
}

export interface TaskResult {
  task_id: string
  status: TaskStatus
  mode: TaskMode
  created_at: string
  started_at?: string
  finished_at?: string
  total_sites: number
  processed_sites: number
  found_records: number
  error_count: number
  elapsed_seconds?: number
  result_file?: string
  log_file?: string
  target_positions?: string[]
}

export interface TaskListItem {
  task_id: string
  status: TaskStatus
  mode: TaskMode
  created_at: string
  finished_at?: string
  total_sites: number
  processed_sites: number
  found_records: number
  error_count: number
}

export interface CreateTaskRequest {
  mode: TaskMode
  target_positions?: string[]
}

export interface CreateTaskResponse {
  task_id: string
  status: TaskStatus
  message: string
}

export interface BlacklistEntry {
  domain: string
  reason?: string
  added_at: string
}

export interface BlacklistResponse {
  added: number
  skipped: number
  total: number
  entries: BlacklistEntry[]
}

export interface ApiError {
  detail: string
  status_code?: number
}

export interface PaginatedTasks {
  items: TaskListItem[]
  total: number
  page: number
  page_size: number
}

export interface UploadFileInfo {
  filename: string
  size_bytes: number
  rows_count: number
  preview_urls: string[]
}

export interface WSMessage {
  type: 'progress' | 'completed' | 'error' | 'ping'
  data: TaskProgress | TaskResult | { message: string }
}
