import axios, { AxiosError } from 'axios'
import type {
  TaskResponse,
  BlacklistUploadResponse,
  UploadFileInfo,
  ApiError,
  DashboardStats,
  LLMStatus,
  SystemStatus,
  AIChatRequest,
  AIChatResponse,
  BlacklistData,
  AppSettings,
} from './types'

// Base API client
const api = axios.create({
  baseURL: '/api',
  timeout: 60_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor — normalise errors
api.interceptors.response.use(
  (res) => res,
  (err: AxiosError<ApiError>) => {
    const message =
      err.response?.data?.detail ??
      err.message ??
      'Неизвестная ошибка сервера'
    return Promise.reject(new Error(message))
  }
)

// ── Tasks ────────────────────────────────────────────────────────────────────────────

/**
 * Create a new parsing task.
 * Always uses mode=2 (all positions) and variant=B (AI / Perplexity).
 */
export async function createTask(
  file: File,
  options?: { max_pages?: number; llm_normalize?: boolean }
): Promise<TaskResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('mode', '2')
  form.append('variant', 'B')
  if (options?.max_pages) form.append('max_pages', String(options.max_pages))
  if (options?.llm_normalize !== undefined)
    form.append('llm_normalize', String(options.llm_normalize))
  const { data } = await api.post<TaskResponse>('/tasks', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * Create task from a single URL for quick parse.
 */
export async function createTaskFromUrl(
  url: string,
  options?: { max_pages?: number; llm_normalize?: boolean }
): Promise<TaskResponse> {
  const { data } = await api.post<TaskResponse>('/tasks/url', {
    url,
    mode: 2,
    variant: 'B',
    max_pages: options?.max_pages,
    llm_normalize: options?.llm_normalize,
  })
  return data
}

/**
 * List all tasks.
 */
export async function listTasks(
  limit = 50,
  offset = 0
): Promise<TaskResponse[]> {
  const { data } = await api.get<TaskResponse[]>('/tasks', {
    params: { limit, offset },
  })
  return data
}

/**
 * Get detailed info about a specific task.
 */
export async function getTask(taskId: string): Promise<TaskResponse> {
  const { data } = await api.get<TaskResponse>(`/tasks/${taskId}`)
  return data
}

/**
 * Cancel a running task (DELETE method).
 */
export async function cancelTask(taskId: string): Promise<{ message: string }> {
  const { data } = await api.delete<{ message: string }>(`/tasks/${taskId}`)
  return data
}

/**
 * Delete a task and its associated files.
 */
export async function deleteTask(taskId: string): Promise<{ message: string }> {
  const { data } = await api.delete<{ message: string }>(`/tasks/${taskId}`)
  return data
}

// ── File download helpers ──────────────────────────────────────────────────────────────

/**
 * Download the Excel results file for a task.
 */
export async function downloadResults(taskId: string): Promise<void> {
  const response = await api.get(`/tasks/${taskId}/results`, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  const filename =
    response.headers['content-disposition']
      ?.split('filename=')[1]
      ?.replace(/"/g, '') ?? `results_${taskId}.xlsx`
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

/**
 * Download the log file for a task.
 */
export async function downloadLogs(taskId: string): Promise<void> {
  const response = await api.get(`/tasks/${taskId}/logs`, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([response.data]))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `logs_${taskId}.txt`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// ── Preview ───────────────────────────────────────────────────────────────────────────

/**
 * Validate uploaded file and get preview.
 */
export async function previewFile(file: File): Promise<UploadFileInfo> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<UploadFileInfo>('/upload/preview', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

// ── Blacklist ────────────────────────────────────────────────────────────────────────────

/**
 * Upload blacklist file (txt or xlsx with domains).
 */
export async function uploadBlacklist(file: File): Promise<BlacklistUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<BlacklistUploadResponse>('/blacklist', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * Get current blacklist stats.
 */
export async function getBlacklist(): Promise<BlacklistData> {
  const { data } = await api.get('/blacklist')
  return data
}

/**
 * Add entry to blacklist.
 */
export async function addBlacklistEntry(
  value: string,
  type: 'domain' | 'email' | 'inn'
): Promise<{ message: string }> {
  const { data } = await api.post('/blacklist/entry', { value, type })
  return data
}

/**
 * Remove entry from blacklist.
 */
export async function removeBlacklistEntry(id: string): Promise<{ message: string }> {
  const { data } = await api.delete(`/blacklist/entry/${id}`)
  return data
}

// ── WebSocket helper ──────────────────────────────────────────────────────────────

/**
 * Create a WebSocket connection to receive real-time task updates.
 * Returns the WebSocket instance so the caller can manage lifecycle.
 */
export function connectTaskWebSocket(
  taskId: string,
  onMessage: (event: MessageEvent) => void,
  onClose?: (event: CloseEvent) => void,
  onError?: (event: Event) => void
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.host
  const ws = new WebSocket(`${protocol}://${host}/api/ws/${taskId}`)
  ws.addEventListener('message', onMessage)
  if (onClose) ws.addEventListener('close', onClose)
  if (onError) ws.addEventListener('error', onError)
  return ws
}

// ── Dashboard & Stats ──────────────────────────────────────────────────────────────

/**
 * Get dashboard statistics.
 */
export async function getDashboardStats(): Promise<DashboardStats> {
  try {
    const { data } = await api.get<DashboardStats>('/dashboard/stats')
    return data
  } catch {
    // Fallback: build stats from tasks list
    const tasks = await listTasks(100, 0)
    const totalContacts = tasks.reduce((sum, t) => sum + (t.progress?.contacts_found ?? 0), 0)
    const totalSites = tasks.reduce((sum, t) => sum + (t.progress?.total_sites ?? 0), 0)
    const avgSpeed = tasks.length > 0
      ? tasks.reduce((sum, t) => sum + (t.progress?.elapsed_seconds ?? 0), 0) / tasks.length
      : 0

    // Build contacts by day from last 7 days
    const now = new Date()
    const contactsByDay: { date: string; count: number }[] = []
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now)
      d.setDate(d.getDate() - i)
      const dateStr = d.toISOString().split('T')[0]
      const dayTasks = tasks.filter(t => t.created_at?.startsWith(dateStr))
      contactsByDay.push({
        date: dateStr,
        count: dayTasks.reduce((s, t) => s + (t.progress?.contacts_found ?? 0), 0),
      })
    }

    return {
      total_tasks: tasks.length,
      total_contacts: totalContacts,
      total_sites_processed: totalSites,
      avg_speed: Math.round(avgSpeed),
      contacts_by_day: contactsByDay,
      recent_tasks: tasks.slice(0, 5),
    }
  }
}

/**
 * Get LLM status.
 */
export async function getLLMStatus(): Promise<LLMStatus> {
  try {
    const { data } = await api.get<LLMStatus>('/llm/status')
    return data
  } catch {
    return {
      model_name: 'Неизвестно',
      tokens_used_today: 0,
      avg_response_time: 0,
      is_connected: false,
    }
  }
}

/**
 * Get system status.
 */
export async function getSystemStatus(): Promise<SystemStatus> {
  try {
    const { data } = await api.get<SystemStatus>('/system/status')
    return data
  } catch {
    return {
      backend_healthy: false,
      llm_connected: false,
      disk_usage_percent: 0,
      uptime_seconds: 0,
      version: 'N/A',
    }
  }
}

// ── AI Chat ──────────────────────────────────────────────────────────────────────────

/**
 * Send a message to the AI assistant.
 */
export async function sendAIMessage(request: AIChatRequest): Promise<AIChatResponse> {
  const { data } = await api.post<AIChatResponse>('/ai/chat', request)
  return data
}

// ── Settings ─────────────────────────────────────────────────────────────────────────

/**
 * Get current app settings.
 */
export async function getSettings(): Promise<AppSettings> {
  try {
    const { data } = await api.get<AppSettings>('/settings')
    return data
  } catch {
    return {
      llm_model: '',
      llm_api_url: '',
      llm_api_key: '',
      llm_timeout: 30,
      max_pages_per_site: 50,
      concurrent_browsers: 3,
      request_delay: 1000,
    }
  }
}

/**
 * Update app settings.
 */
export async function updateSettings(settings: Partial<AppSettings>): Promise<AppSettings> {
  const { data } = await api.put<AppSettings>('/settings', settings)
  return data
}

export default api
