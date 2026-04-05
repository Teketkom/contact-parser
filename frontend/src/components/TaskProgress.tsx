import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Loader2,
  Globe,
  Users,
  Coins,
  AlertTriangle,
  Clock,
  XCircle,
  CheckCircle2,
  Download,
  FileText,
  StopCircle,
  ArrowRight,
  Terminal,
  BarChart3,
} from 'lucide-react'
import { getTask, cancelTask, downloadResults, downloadLogs, connectTaskWebSocket } from '../api'
import type { TaskResponse, WSMessage } from '../types'

export default function TaskProgress() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [task, setTask] = useState<TaskResponse | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [cancelling, setCancelling] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Auto-scroll logs
  const scrollToBottom = useCallback(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [logs, scrollToBottom])

  // Load initial task
  useEffect(() => {
    if (!taskId) return
    let cancelled = false

    async function loadTask() {
      try {
        const data = await getTask(taskId!)
        if (!cancelled) {
          setTask(data)
          setLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Ошибка загрузки задачи')
          setLoading(false)
        }
      }
    }

    loadTask()
    return () => { cancelled = true }
  }, [taskId])

  // WebSocket connection
  useEffect(() => {
    if (!taskId) return

    const ws = connectTaskWebSocket(
      taskId,
      (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data)
          switch (msg.type) {
            case 'progress':
              setTask(prev => prev ? {
                ...prev,
                status: 'running',
                progress: { ...prev.progress, ...msg.data },
              } : prev)
              break
            case 'log': {
              const logLine = String(msg.data.message ?? msg.data.line ?? JSON.stringify(msg.data))
              setLogs(prev => [...prev.slice(-500), logLine])
              break
            }
            case 'completed':
              setTask(prev => prev ? { ...prev, status: 'completed', progress: { ...prev.progress, ...msg.data } } : prev)
              break
            case 'error':
              setTask(prev => prev ? {
                ...prev,
                status: 'failed',
                error_message: String(msg.data.message ?? msg.data.error ?? 'Неизвестная ошибка'),
              } : prev)
              break
            case 'cancelled':
              setTask(prev => prev ? { ...prev, status: 'cancelled' } : prev)
              break
          }
        } catch {
          // Non-JSON message, treat as log
          setLogs(prev => [...prev.slice(-500), event.data])
        }
      },
      () => {
        // Reconnect on close if task still running
        setTimeout(() => {
          if (wsRef.current) {
            getTask(taskId).then(setTask).catch(() => {})
          }
        }, 3000)
      },
      () => {
        console.error('WebSocket error')
      }
    )

    wsRef.current = ws
    return () => {
      wsRef.current = null
      ws.close()
    }
  }, [taskId])

  // Polling fallback
  useEffect(() => {
    if (!taskId) return
    const interval = setInterval(async () => {
      try {
        const data = await getTask(taskId)
        setTask(data)
      } catch {}
    }, 5000)
    return () => clearInterval(interval)
  }, [taskId])

  const handleCancel = async () => {
    if (!taskId) return
    setCancelling(true)
    try {
      await cancelTask(taskId)
      const data = await getTask(taskId)
      setTask(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка отмены')
    } finally {
      setCancelling(false)
    }
  }

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}с`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}м ${Math.round(seconds % 60)}с`
    return `${Math.floor(seconds / 3600)}ч ${Math.round((seconds % 3600) / 60)}м`
  }

  const getLogLineClass = (line: string): string => {
    const lower = line.toLowerCase()
    if (lower.includes('error') || lower.includes('ошибка') || lower.includes('fail')) return 'terminal-line-error'
    if (lower.includes('success') || lower.includes('найден') || lower.includes('готово') || lower.includes('completed')) return 'terminal-line-success'
    if (lower.includes('warn') || lower.includes('предупреждение') || lower.includes('retry')) return 'terminal-line-warn'
    return 'terminal-line-info'
  }

  const isFinished = task?.status === 'completed' || task?.status === 'failed' || task?.status === 'cancelled'
  const percent = task?.progress?.percent ?? 0

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    )
  }

  if (error && !task) {
    return (
      <div className="animate-fade-in">
        <div className="glass-card p-8 text-center">
          <XCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-3">
            Задача
            <span className="font-mono text-sm text-slate-400 bg-slate-800/50 px-2 py-0.5 rounded">
              {taskId?.slice(0, 8)}
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {task?.status === 'running' ? 'Выполняется парсинг...' :
              task?.status === 'completed' ? 'Задача завершена' :
              task?.status === 'failed' ? 'Задача завершилась с ошибкой' :
              task?.status === 'cancelled' ? 'Задача отменена' :
              'Ожидание...'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {task?.status === 'running' && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors"
            >
              {cancelling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <StopCircle className="w-3.5 h-3.5" />}
              Отменить
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-slate-300">Прогресс</span>
          <span className="text-sm font-bold text-blue-400">{Math.round(percent)}%</span>
        </div>
        <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${
              task?.status === 'completed' ? 'bg-gradient-to-r from-emerald-500 to-green-500' :
              task?.status === 'failed' ? 'bg-red-500' :
              task?.status === 'cancelled' ? 'bg-slate-600' :
              'bg-gradient-to-r from-blue-500 to-cyan-500 progress-striped'
            }`}
            style={{ width: `${Math.min(percent, 100)}%` }}
          />
        </div>
        {task?.progress?.current_site && task.status === 'running' && (
          <div className="flex items-center gap-2 mt-3">
            <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />
            <span className="text-xs text-slate-400 truncate">
              {task.progress.current_site}
            </span>
          </div>
        )}
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard
          icon={Globe}
          label="Страниц"
          value={`${task?.progress?.processed_sites ?? 0}/${task?.progress?.total_sites ?? 0}`}
          color="blue"
        />
        <StatCard
          icon={Users}
          label="Контактов"
          value={String(task?.progress?.contacts_found ?? 0)}
          color="green"
        />
        <StatCard
          icon={BarChart3}
          label="Страницы"
          value={String(task?.progress?.total_pages ?? 0)}
          color="purple"
        />
        <StatCard
          icon={Coins}
          label="LLM токены"
          value={String(task?.progress?.llm_tokens_used ?? 0)}
          color="amber"
        />
        <StatCard
          icon={AlertTriangle}
          label="Ошибки"
          value={String(task?.progress?.errors ?? 0)}
          color="red"
        />
        <StatCard
          icon={Clock}
          label="Время"
          value={formatTime(task?.progress?.elapsed_seconds ?? 0)}
          color="slate"
        />
      </div>

      {/* Live log terminal */}
      <div className="glass-card overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-800/50 bg-slate-900/30">
          <Terminal className="w-4 h-4 text-slate-500" />
          <span className="text-xs font-medium text-slate-400">Журнал выполнения</span>
          <div className="flex-1" />
          {task?.status === 'running' && (
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] text-slate-500">Live</span>
            </span>
          )}
        </div>
        <div ref={logRef} className="terminal max-h-[300px] rounded-none border-0">
          {logs.length === 0 ? (
            <p className="text-slate-600 text-center py-4">Ожидание логов...</p>
          ) : (
            logs.map((line, i) => (
              <div key={i} className={`terminal-line ${getLogLineClass(line)}`}>
                {line}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Completed section */}
      {isFinished && (
        <div className="glass-card p-6">
          <div className="flex items-center gap-3 mb-4">
            {task?.status === 'completed' ? (
              <CheckCircle2 className="w-6 h-6 text-emerald-400" />
            ) : task?.status === 'failed' ? (
              <XCircle className="w-6 h-6 text-red-400" />
            ) : (
              <StopCircle className="w-6 h-6 text-slate-400" />
            )}
            <h2 className="text-lg font-semibold text-white">
              {task?.status === 'completed' ? 'Задача завершена' :
                task?.status === 'failed' ? 'Ошибка выполнения' :
                'Задача отменена'}
            </h2>
          </div>

          {task?.error_message && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <p className="text-sm text-red-400">{task.error_message}</p>
            </div>
          )}

          {task?.status === 'completed' && (
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => navigate(`/tasks/${taskId}/results`)}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 transition-colors"
              >
                <ArrowRight className="w-4 h-4" />
                Посмотреть результаты
              </button>
              <button
                onClick={() => taskId && downloadResults(taskId)}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
              >
                <Download className="w-4 h-4" />
                Скачать Excel
              </button>
              <button
                onClick={() => taskId && downloadLogs(taskId)}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-slate-400 border border-slate-700 hover:bg-slate-800/50 transition-colors"
              >
                <FileText className="w-4 h-4" />
                Скачать логи
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Stat Card ─────────────────────────────────────────────────────────────────

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType
  label: string
  value: string
  color: string
}) {
  const colorMap: Record<string, string> = {
    blue: 'text-blue-400 bg-blue-500/10',
    green: 'text-emerald-400 bg-emerald-500/10',
    purple: 'text-violet-400 bg-violet-500/10',
    amber: 'text-amber-400 bg-amber-500/10',
    red: 'text-red-400 bg-red-500/10',
    slate: 'text-slate-400 bg-slate-500/10',
  }
  const c = colorMap[color] || colorMap.slate

  return (
    <div className="glass-card p-3.5">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-2 ${c}`}>
        <Icon className="w-4 h-4" />
      </div>
      <p className="text-lg font-bold text-white">{value}</p>
      <p className="text-[10px] text-slate-500 mt-0.5">{label}</p>
    </div>
  )
}
