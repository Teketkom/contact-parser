import axios, { AxiosError } from 'axios'
import type {
  CreateTaskResponse,
  TaskResult,
  TaskProgress,
  PaginatedTasks,
  BlacklistResponse,
  UploadFileInfo,
  TaskMode,
  ApiError,
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
 * Uploads the sites file and optional params.
 */
export async function createTask(
  file: File,
  mode: TaskMode,
  targetPositions?: string[]
): Promise<CreateTaskResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('mode', String(mode))
  if (targetPositions && targetPositions.length > 0) {
    form.append('target_positions', targetPositions.join(','))
  }
  const { data } = await api.post<CreateTaskResponse>('/tasks', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * List all tasks with pagination.
 */
export async function listTasks(
  page = 1,
  pageSize = 20
): Promise<PaginatedTasks> {
  const { data } = await api.get<PaginatedTasks>('/tasks', {
    params: { page, page_size: pageSize },
  })
  return data
}

/**
 * Get detailed info about a specific task.
 */
export async function getTask(taskId: string): Promise<TaskResult> {
  const { data } = await api.get<TaskResult>(`/tasks/${taskId}`)
  return data
}

/**
 * Get current progress of a running task (polling fallback).
 */
export async function getTaskProgress(taskId: string): Promise<TaskProgress> {
  const { data } = await api.get<TaskProgress>(`/tasks/${taskId}/progress`)
  return data
}

/**
 * Cancel a running task.
 */
export async function cancelTask(taskId: string): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>(`/tasks/${taskId}/cancel`)
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
  const response = await api.get(`/tasks/${taskId}/download`, {
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
export async function uploadBlacklist(file: File): Promise<BlacklistResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<BlacklistResponse>('/blacklist/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * Get current blacklist entries.
 */
export async function getBlacklist(): Promise<{ entries: { domain: string; reason?: string; added_at: string }[]; total: number }> {
  const { data } = await api.get('/blacklist')
  return data
}

/**
 * Remove a domain from the blacklist.
 */
export async function removeFromBlacklist(domain: string): Promise<{ message: string }> {
  const { data } = await api.delete(`/blacklist/${encodeURIComponent(domain)}`)
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
  const ws = new WebSocket(`${protocol}://${host}/ws/tasks/${taskId}`)
  ws.addEventListener('message', onMessage)
  if (onClose) ws.addEventListener('close', onClose)
  if (onError) ws.addEventListener('error', onError)
  return ws
}

export default api
