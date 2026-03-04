import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Loader2, Globe, CheckCircle2, XCircle, AlertTriangle,
  Clock, Users, Activity, StopCircle
} from 'lucide-react'
import { connectTaskWebSocket, getTaskProgress, cancelTask } from '../api'
import type { TaskProgress as ITaskProgress, WSMessage, TaskStatus } from '../types'

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
  completed: 'Завершено',
  failed:    'Ошибка',
  cancelled: 'Отменено',
}

const statusColor: Record<TaskStatus, string> = {
  pending:   'bg-amber-100 text-amber-700',
  running:   'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed:    'bg-red-100 text-red-700',
  cancelled: 'bg-slate-100 text-slate-600',
}

export default function TaskProgress({ taskId, onCompleted }: TaskProgressProps) {
  const [progress, setProgress] = useState<ITaskProgress | null>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const [cancelConfirm, setCancelConfirm] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const navigate = useNavigate()

  const startPolling = useCallback(() => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const p = await getTaskProgress(taskId)
        setProgress(p)
        if (p.status === 'completed' || p.status === 'failed' || p.status === 'cancelled') {
          if (pollRef.current) clearInterval(pollRef.current)
          if (p.status === 'completed') onCompleted()
        }
      } catch { /* ignore */ }
    }, 2000)
  }, [taskId, onCompleted])

  useEffect(() => {
    try {
      const ws = connectTaskWebSocket(
        taskId,
        (e: MessageEvent) => {
          try {
            const msg = JSON.parse(e.data) as WSMessage
            if (msg.type === 'progress') {
              setProgress(msg.data as ITaskProgress)
            } else if (msg.type === 'completed') {
              setProgress(msg.data as ITaskProgress)
              onCompleted()
            } else if (msg.type === 'error') {
              setProgress((prev) => prev ? { ...prev, status: 'failed' } : null)
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

    getTaskProgress(taskId).then(setProgress).catch(() => {})

    return () => {
      wsRef.current?.close()
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [taskId, onCompleted, startPolling])

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

  const pct = progress && progress.total_sites > 0
    ? Math.round((progress.processed_sites / progress.total_sites) * 100)
    : 0

  const isFinished = progress?.status === 'completed'
    || progress?.status === 'failed'
    || progress?.status === 'cancelled'

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Выполнение задачи</h1>
          <p className="text-slate-400 text-xs font-mono mt-0.5">{taskId}</p>
        </div>
        {progress?.status && (
          <span className={`status-badge text-xs ${statusColor[progress.status]}`}>
            {progress.status === 'running' && (
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
            )}
            {statusLabel[progress.status]}
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
          {progress?.status === 'running' && progress.total_sites === 0 ? (
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

        {progress?.estimated_remaining_seconds != null && progress.status === 'running' && (
          <p className="text-xs text-slate-400 mt-1.5 text-right">
            Осталось примерно {formatDuration(progress.estimated_remaining_seconds)}
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
            {progress?.found_records ?? 0}
          </p>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 text-slate-500 text-xs mb-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            Ошибок
          </div>
          <p className={`text-2xl font-bold ${(progress?.error_count ?? 0) > 0 ? 'text-amber-600' : 'text-slate-900'}`}>
            {progress?.error_count ?? 0}
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

      {progress?.current_site && progress.status === 'running' && (
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

      {progress?.errors && progress.errors.length > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            Ошибки ({progress.errors.length})
          </h3>
          <ul className="space-y-1.5 max-h-40 overflow-y-auto">
            {progress.errors.map((err, i) => (
              <li key={i} className="text-xs text-red-600 font-mono bg-red-50 px-3 py-1.5 rounded-lg">
                {err}
              </li>
            ))}
          </ul>
        </div>
      )}

      {progress?.status === 'completed' && (
        <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-xl text-green-700">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          <div>
            <p className="font-semibold text-sm">Парсинг успешно завершён</p>
            <p className="text-xs text-green-600">Найдено {progress.found_records} записей</p>
          </div>
        </div>
      )}

      {progress?.status === 'failed' && (
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700">
          <XCircle className="w-5 h-5 flex-shrink-0" />
          <div>
            <p className="font-semibold text-sm">Задача завершилась с ошибкой</p>
            <p className="text-xs text-red-500">{progress.message}</p>
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
        {isFinished && progress?.status === 'completed' && (
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
