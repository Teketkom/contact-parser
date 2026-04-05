import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ListTodo,
  Download,
  Trash2,
  Loader2,
  RefreshCw,
  ChevronUp,
  ChevronDown,
  CheckSquare,
  Square,
  AlertCircle,
} from 'lucide-react'
import { listTasks, downloadResults, deleteTask } from '../api'
import type { TaskResponse } from '../types'

type SortField = 'task_id' | 'status' | 'total_sites' | 'contacts_found' | 'elapsed_seconds' | 'created_at'
type SortDir = 'asc' | 'desc'

function statusBadge(status: string) {
  const config: Record<string, { class: string; label: string }> = {
    running: { class: 'badge-running', label: 'В работе' },
    completed: { class: 'badge-completed', label: 'Готово' },
    failed: { class: 'badge-failed', label: 'Ошибка' },
    cancelled: { class: 'badge-cancelled', label: 'Отменено' },
    pending: { class: 'badge-pending', label: 'Ожидание' },
    paused: { class: 'badge-pending', label: 'Пауза' },
  }
  const cfg = config[status] || config.pending
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.class}`}>
      {status === 'running' && <Loader2 className="w-3 h-3 animate-spin" />}
      {cfg.label}
    </span>
  )
}

export default function TaskList() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<TaskResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortField, setSortField] = useState<SortField>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [deleting, setDeleting] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listTasks(100, 0)
      setTasks(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 15_000)
    return () => clearInterval(interval)
  }, [])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('desc')
    }
  }

  const sorted = [...tasks].sort((a, b) => {
    let valA: number | string = ''
    let valB: number | string = ''
    switch (sortField) {
      case 'task_id': valA = a.task_id; valB = b.task_id; break
      case 'status': valA = a.status; valB = b.status; break
      case 'total_sites': valA = a.progress?.total_sites ?? 0; valB = b.progress?.total_sites ?? 0; break
      case 'contacts_found': valA = a.progress?.contacts_found ?? 0; valB = b.progress?.contacts_found ?? 0; break
      case 'elapsed_seconds': valA = a.progress?.elapsed_seconds ?? 0; valB = b.progress?.elapsed_seconds ?? 0; break
      case 'created_at': valA = a.created_at; valB = b.created_at; break
    }
    if (typeof valA === 'string') {
      return sortDir === 'asc' ? valA.localeCompare(valB as string) : (valB as string).localeCompare(valA)
    }
    return sortDir === 'asc' ? (valA as number) - (valB as number) : (valB as number) - (valA as number)
  })

  const toggleSelect = (id: string) => {
    const s = new Set(selected)
    if (s.has(id)) s.delete(id)
    else s.add(id)
    setSelected(s)
  }

  const toggleSelectAll = () => {
    if (selected.size === sorted.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(sorted.map(t => t.task_id)))
    }
  }

  const handleDeleteSelected = async () => {
    if (selected.size === 0) return
    setDeleting(true)
    try {
      await Promise.all([...selected].map(id => deleteTask(id)))
      setSelected(new Set())
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка удаления')
    } finally {
      setDeleting(false)
    }
  }

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}с`
    if (seconds < 3600) return `${Math.round(seconds / 60)}м ${Math.round(seconds % 60)}с`
    return `${Math.floor(seconds / 3600)}ч ${Math.round((seconds % 3600) / 60)}м`
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="opacity-0 group-hover:opacity-30"><ChevronUp className="w-3 h-3" /></span>
    return sortDir === 'asc' ? <ChevronUp className="w-3 h-3 text-blue-400" /> : <ChevronDown className="w-3 h-3 text-blue-400" />
  }

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Задачи</h1>
          <p className="text-sm text-slate-400 mt-1">Все задачи парсинга с их статусами</p>
        </div>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <button
              onClick={handleDeleteSelected}
              disabled={deleting}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors"
            >
              {deleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
              Удалить ({selected.size})
            </button>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 border border-slate-700 hover:border-slate-600 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Обновить
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
          <AlertCircle className="w-4 h-4 text-red-400" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Table */}
      <div className="glass-card overflow-hidden">
        {loading && tasks.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
          </div>
        ) : sorted.length === 0 ? (
          <div className="text-center py-16">
            <ListTodo className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <p className="text-sm text-slate-500">Нет задач</p>
            <p className="text-xs text-slate-600 mt-1">Создайте новую задачу для начала работы</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="dark-table">
              <thead>
                <tr>
                  <th className="w-10">
                    <button onClick={toggleSelectAll} className="text-slate-500 hover:text-slate-300">
                      {selected.size === sorted.length && sorted.length > 0 ? (
                        <CheckSquare className="w-4 h-4" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                    </button>
                  </th>
                  <th className="group cursor-pointer" onClick={() => handleSort('task_id')}>
                    <span className="flex items-center gap-1">ID <SortIcon field="task_id" /></span>
                  </th>
                  <th className="group cursor-pointer" onClick={() => handleSort('status')}>
                    <span className="flex items-center gap-1">Статус <SortIcon field="status" /></span>
                  </th>
                  <th className="group cursor-pointer" onClick={() => handleSort('total_sites')}>
                    <span className="flex items-center gap-1">Сайты <SortIcon field="total_sites" /></span>
                  </th>
                  <th className="group cursor-pointer" onClick={() => handleSort('contacts_found')}>
                    <span className="flex items-center gap-1">Контакты <SortIcon field="contacts_found" /></span>
                  </th>
                  <th className="group cursor-pointer" onClick={() => handleSort('elapsed_seconds')}>
                    <span className="flex items-center gap-1">Время <SortIcon field="elapsed_seconds" /></span>
                  </th>
                  <th className="group cursor-pointer" onClick={() => handleSort('created_at')}>
                    <span className="flex items-center gap-1">Создано <SortIcon field="created_at" /></span>
                  </th>
                  <th className="w-16">Действия</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((task) => (
                  <tr
                    key={task.task_id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/tasks/${task.task_id}`)}
                  >
                    <td onClick={(e) => e.stopPropagation()}>
                      <button onClick={() => toggleSelect(task.task_id)} className="text-slate-500 hover:text-slate-300">
                        {selected.has(task.task_id) ? (
                          <CheckSquare className="w-4 h-4 text-blue-400" />
                        ) : (
                          <Square className="w-4 h-4" />
                        )}
                      </button>
                    </td>
                    <td>
                      <span className="font-mono text-xs text-slate-300">{task.task_id.slice(0, 8)}</span>
                    </td>
                    <td>{statusBadge(task.status)}</td>
                    <td className="text-xs">{task.progress?.total_sites ?? 0}</td>
                    <td className="text-xs font-medium text-emerald-400">{task.progress?.contacts_found ?? 0}</td>
                    <td className="text-xs">{formatTime(task.progress?.elapsed_seconds ?? 0)}</td>
                    <td className="text-xs">
                      {new Date(task.created_at).toLocaleString('ru-RU', {
                        day: '2-digit', month: '2-digit', year: '2-digit',
                        hour: '2-digit', minute: '2-digit',
                      })}
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      {task.status === 'completed' && task.result_file && (
                        <button
                          onClick={() => downloadResults(task.task_id)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-blue-400 hover:bg-blue-500/10 transition-colors"
                          title="Скачать результаты"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
