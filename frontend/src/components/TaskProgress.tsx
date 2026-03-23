import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Loader2, Globe, CheckCircle2, XCircle, AlertTriangle,
  Clock, Users, Activity, StopCircle
} from 'lucide-react'
import { connectTaskWebSocket, getTask, cancelTask } from '../api'
import type { TaskResponse, TaskProgress as ITaskProgress, WSMessage, TaskStatus } from '../types'

interface TaskProgressProps {
  taskId: string
  onCompleted: () => void
}

const formatDuration = (seconds: number): string => {
  if (seconds < 60) return `${Math.round(seconds)} с`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  if (m < 60) return `${m} мин ${s} с`
  const h = Math.floor(m / 60)
  return `${h} ч ${m % 60} мин`
}

const statusLabel: Record<TaskStatus, string> = {
  pending:   'Ожидание',
  running:   'Выполняется',
  paused:    'Приостановлена',
  completed: 'Завершено',
  failed:    'Ошибка',
  cancelled: 'Отменено',
}

const statusColor: Record<TaskStatus, string> = {
  pending:   'bg-amber-100 text-amber-700',
  running:   'bg-blue-100 text-blue-700',
  paused:    'bg-purple-100 text-purple-700',
  completed: 'bg-green-100 text-green-700',
  failed:    'bg-red-100 text-red-700',
  cancelled: 'bg-slate-100 text-slate-600',
}

export default function TaskProgress({ taskId, onCompleted }: TaskProgressProps) {
  const [taskData, setTaskData] = useState<TaskResponse | null>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const [cancelConfirm, setCancelConfirm] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const navigate = useNavigate()

  const updateFromTask = useCallback((t: TaskResponse) => {
    setTaskData(t)
    if (t.status === 'completed') onCompleted()
  }, [onCompleted])

  const startPolling = useCallback(() => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const t = await getTask(taskId)
        updateFromTask(t)
        if (t.status === 'completed' || t.status === 'failed' || t.status === 'cancelled') {
          if (pollRef.current) clearInterval(pollRef.current)
        }
      } catch { /* ignore */ }
    }, 2000)
  }, [taskId, updateFromTask])

  useEffect(() => {
    try {
      const ws = connectTaskWebSocket(
        taskId,
        (e: MessageEvent) => {
          try {
            const msg = JSON.parse(e.data) as WSMessage
            if (msg.type === 'progress' && msg.data) {
              setTaskData(prev => prev ? { ...prev, progress: msg.data as unknown as ITaskProgress, status: 'running' } : prev)
            } else if (msg.type === 'completed') {
              setTaskData(prev => prev ? { ...prev, status: 'completed' } : prev)
              onCompleted()
            } else if (msg.type === 'error') {
              setTaskData(prev => prev ? { ...prev, status: 'failed', error_message: (msg.data as Record<string, string>)?.message } : prev)
            } else if (msg.type === 'cancelled') {
              setTaskData(prev => prev ? { ...prev, status: 'cancelled' } : prev)
            }
          } catch { /* ignore parse errors */ }
        },
        () => {
          setWsConnected(false)
          startPolling()
        },
        () => {
          setWsConnected(false)
          startPolling()
        }
      )
      ws.addEventListener('open', () => {
        setWsConnected(true)
        if (pollRef.current) {
          clearInterval(pollRef.current)
          pollRef.current = null
        }
      })
      wsRef.current = ws
    } catch {
      startPolling()
    }

    // Initial fetch
    getTask(taskId).then(updateFromTask).catch(() => {})

    return () => {
      wsRef.current?.close()
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [taskId, onCompleted, startPolling, updateFromTask])

  const handleCancel = async () => {
    if (!cancelConfirm) { setCancelConfirm(true); return }
    setCancelling(true)
    try {
      await cancelTask(taskId)
    } catch { /* ignore */ } finally {
      setCancelling(false)
      setCancelConfirm(false)
    }
  }

  const progress = taskData?.progress
  const pct = progress && progress.total_sites > 0
    ? Math.round((progress.processed_sites / progress.total_sites) * 100)
    : (taskData?.status === 'completed' ? 100 : 0)

  const isFinished = taskData?.status === 'completed'
    || taskData?.status === 'failed'
    || taskData?.status === 'cancelled'

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Выполнение задачи</h1>
          <p className="text-slate-400 text-xs font-mono mt-0.5">{taskId}</p>
        </div>
        {taskData?.status && (
          <span className={`status-badge text-xs ${statusColor[taskData.status] ?? ''}`}>
            {taskData.status === 'running' && (
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
            )}
            {statusLabel[taskData.status] ?? taskData.status}
          </span>
        )}
      </div>

      <div className="card p-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-slate-700">
            Обработано {progress?.processed_sites ?? 0} из {progress?.total_sites ?? '…'} сайтов
          </span>
          <span className="text-sm font-semibold text-primary-600">{pct}%</span>
        </div>

        <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
          {taskData?.status === 'running' && progress?.total_sites === 0 ? (
            <div
              className="h-full bg-primary-500 rounded-full relative overflow-hidden"
              style={{ width: '100%' }}
            >
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-[progress-indeterminate_1.5s_ease-in-out_infinite]" />
            </div>
          ) : (
            <div
              className="h-full bg-primary-500 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${pct}%` }}
            />
          )}
        </div>

        {progress?.eta_seconds != null && taskData?.status === 'running' && (
          <p className="text-xs text-slate-400 mt-1.5 text-right">
            Осталось примерно {formatDuration(progress.eta_seconds)}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="card p-4">
          <div className="flex items-center gap-2 text-slate-500 text-xs mb-1.5">
            <Users className="w-3.5 h-3.5" />
            Найдено записей
          </div>
          <p className="text-2xl font-bold text-slate-900">
            {progress?.contacts_found ?? 0}
          </p>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 text-slate-500 text-xs mb-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            Ошибок
          </div>
          <p className={`text-2xl font-bold ${(progress?.errors ?? 0) > 0 ? 'text-amber-600' : 'text-slate-900'}`}>
            {progress?.errors ?? 0}
          </p>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 text-slate-500 text-xs mb-1.5">
            <Clock className="w-3.5 h-3.5" />
            Время
          </div>
          <p className="text-2xl font-bold text-slate-900">
            {formatDuration(progress?.elapsed_seconds ?? 0)}
          </p>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 text-slate-500 text-xs mb-1.5">
            <Activity className="w-3.5 h-3.5" />
            Соединение
          </div>
          <p className={`text-sm font-semibold mt-1 ${wsConnected ? 'text-green-600' : 'text-amber-500'}`}>
            {wsConnected ? 'WebSocket' : 'Опрос'}
          </p>
        </div>
      </div>

      {progress?.current_site && taskData?.status === 'running' && (
        <div className="card p-4 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary-50 flex items-center justify-center flex-shrink-0">
            <Globe className="w-4 h-4 text-primary-600 animate-pulse" />
          </div>
          <div className="min-w-0">
            <p className="text-xs text-slate-400 mb-0.5">Обрабатывается сейчас</p>
            <p className="text-sm font-mono text-slate-700 truncate">{progress.current_site}</p>
          </div>
          <Loader2 className="w-4 h-4 text-primary-400 animate-spin flex-shrink-0 ml-auto" />
        </div>
      )}

      {taskData?.status === 'completed' && (
        <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-xl text-green-700">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          <div>
            <p className="font-semibold text-sm">Парсинг успешно завершён</p>
            <p className="text-xs text-green-600">Найдено {progress?.contacts_found ?? 0} записей</p>
          </div>
        </div>
      )}

      {taskData?.status === 'failed' && (
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700">
          <XCircle className="w-5 h-5 flex-shrink-0" />
          <div>
            <p className="font-semibold text-sm">Задача завершилась с ошибкой</p>
            {taskData.error_message && (
              <p className="text-xs text-red-500">{taskData.error_message}</p>
            )}
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 flex-wrap">
        {!isFinished && (
          <button
            type="button"
            onClick={handleCancel}
            disabled={cancelling}
            className="flex items-center gap-2 px-4 py-2 border border-red-200 text-red-600 hover:bg-red-50 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            <StopCircle className="w-4 h-4" />
            {cancelConfirm ? 'Подтвердить отмену' : 'Отменить задачу'}
          </button>
        )}
        {cancelConfirm && (
          <button
            type="button"
            onClick={() => setCancelConfirm(false)}
            className="px-4 py-2 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-medium transition-colors"
          >
            Не отменять
          </button>
        )}
        {isFinished && taskData?.status === 'completed' && (
          <button
            type="button"
            onClick={onCompleted}
            className="flex items-center gap-2 px-5 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-semibold transition-colors"
          >
            Посмотреть результаты →
          </button>
        )}
        <button
          type="button"
          onClick={() => navigate('/tasks')}
          className="px-4 py-2 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-medium transition-colors"
        >
          Все задачи
        </button>
      </div>
    </div>
  )
}
