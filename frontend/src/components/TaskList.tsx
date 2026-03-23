import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Clock, CheckCircle2, XCircle, Loader2, AlertCircle,
  RefreshCw, Trash2, Play, Eye
} from 'lucide-react'
import { listTasks, deleteTask } from '../api'
import type { TaskResponse, TaskStatus } from '../types'

const statusLabel: Record<TaskStatus, string> = {
  pending:   'Ожидание',
  running:   'Выполняется',
  paused:    'Приостановлена',
  completed: 'Завершено',
  failed:    'Ошибка',
  cancelled: 'Отменено',
}

const statusColor: Record<TaskStatus, string> = {
  pending:   'bg-amber-50 text-amber-700 border-amber-200',
  running:   'bg-blue-50 text-blue-700 border-blue-200',
  paused:    'bg-purple-50 text-purple-700 border-purple-200',
  completed: 'bg-green-50 text-green-700 border-green-200',
  failed:    'bg-red-50 text-red-600 border-red-200',
  cancelled: 'bg-slate-100 text-slate-500 border-slate-200',
}

const StatusIcon = ({ status }: { status: TaskStatus }) => {
  switch (status) {
    case 'pending':   return <Clock className="w-3.5 h-3.5" />
    case 'running':   return <Loader2 className="w-3.5 h-3.5 animate-spin" />
    case 'completed': return <CheckCircle2 className="w-3.5 h-3.5" />
    case 'failed':    return <XCircle className="w-3.5 h-3.5" />
    case 'cancelled': return <AlertCircle className="w-3.5 h-3.5" />
    default:          return <Clock className="w-3.5 h-3.5" />
  }
}

const modeLabel = (mode: number) => {
  switch (mode) {
    case 1: return 'Режим 1'
    case 2: return 'Режим 2'
    case 3: return 'Режим 3'
    default: return `Режим ${mode}`
  }
}

const formatDate = (iso?: string) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

export default function TaskList() {
  const [tasks, setTasks] = useState<TaskResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const navigate = useNavigate()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await listTasks()
      setTasks(res)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const hasRunning = tasks.some(t => t.status === 'running' || t.status === 'pending')
    if (!hasRunning) return
    const timer = setInterval(() => load(), 3000)
    return () => clearInterval(timer)
  }, [tasks, load])

  const handleDelete = async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setDeletingId(taskId)
    try {
      await deleteTask(taskId)
      setTasks(prev => prev.filter(t => t.task_id !== taskId))
    } catch { /* ignore */ }
    finally { setDeletingId(null) }
  }

  if (loading && tasks.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="card p-8 text-center">
        <XCircle className="w-8 h-8 text-red-300 mx-auto mb-3" />
        <p className="text-red-500 text-sm">{error}</p>
        <button onClick={() => load()} className="mt-4 text-primary-600 text-sm underline">
          Повторить
        </button>
      </div>
    )
  }

  if (tasks.length === 0) {
    return (
      <div className="card p-12 text-center">
        <Play className="w-10 h-10 text-slate-200 mx-auto mb-4" />
        <p className="text-slate-400 text-sm font-medium">Задач пока нет</p>
        <p className="text-slate-300 text-xs mt-1 mb-6">Создайте первую задачу парсинга</p>
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-semibold transition-colors"
        >
          Создать задачу
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">Всего задач: <span className="font-semibold text-slate-700">{tasks.length}</span></p>
        <button
          onClick={() => load()}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 text-slate-500 hover:bg-slate-50 rounded-lg text-sm transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Обновить
        </button>
      </div>

      <div className="card overflow-hidden">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID задачи</th>
              <th>Режим</th>
              <th>Статус</th>
              <th>Прогресс</th>
              <th>Найдено</th>
              <th>Создана</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => {
              const pct = task.progress.total_sites > 0
                ? Math.round((task.progress.processed_sites / task.progress.total_sites) * 100)
                : 0
              return (
                <tr
                  key={task.task_id}
                  onClick={() => navigate(`/tasks/${task.task_id}`)}
                  className="cursor-pointer hover:bg-slate-50 transition-colors"
                >
                  <td>
                    <span className="font-mono text-xs text-slate-500">
                      {task.task_id.slice(0, 8)}…
                    </span>
                  </td>
                  <td>
                    <span className="text-xs font-medium text-slate-600">{modeLabel(task.mode)}</span>
                  </td>
                  <td>
                    <span className={`status-badge border ${statusColor[task.status] ?? statusColor.pending}`}>
                      <StatusIcon status={task.status} />
                      {statusLabel[task.status] ?? task.status}
                    </span>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="w-20 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            task.status === 'completed' ? 'bg-green-500' :
                            task.status === 'failed' ? 'bg-red-400' :
                            'bg-primary-500'
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-400">
                        {task.progress.processed_sites}/{task.progress.total_sites}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className="text-sm font-semibold text-slate-800">{task.progress.contacts_found}</span>
                  </td>
                  <td className="whitespace-nowrap text-xs text-slate-400">
                    {formatDate(task.created_at)}
                  </td>
                  <td>
                    <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                      <button
                        onClick={(e) => { e.stopPropagation(); navigate(`/tasks/${task.task_id}`) }}
                        className="p-1.5 text-slate-400 hover:text-primary-600 rounded-lg hover:bg-primary-50 transition-colors"
                        title="Просмотр"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => handleDelete(task.task_id, e)}
                        disabled={deletingId === task.task_id || task.status === 'running'}
                        className="p-1.5 text-slate-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                        title="Удалить"
                      >
                        {deletingId === task.task_id
                          ? <Loader2 className="w-4 h-4 animate-spin" />
                          : <Trash2 className="w-4 h-4" />
                        }
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
