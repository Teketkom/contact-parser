import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Download, FileText, FileSpreadsheet, Users, AlertTriangle,
  Clock, Globe, ChevronDown, ChevronUp, ExternalLink
} from 'lucide-react'
import { getTask, downloadResults, downloadLogs } from '../api'
import type { TaskResponse, ContactRecord } from '../types'
import api from '../api'

interface TaskResultsProps {
  taskId: string
}

const formatDuration = (seconds?: number): string => {
  if (!seconds) return '—'
  if (seconds < 60) return `${Math.round(seconds)} с`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m} мин ${s} с`
}

export default function TaskResults({ taskId }: TaskResultsProps) {
  const [task, setTask] = useState<TaskResponse | null>(null)
  const [preview, setPreview] = useState<ContactRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [downloadingLogs, setDownloadingLogs] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        const t = await getTask(taskId)
        setTask(t)
        try {
          const { data } = await api.get<ContactRecord[]>(`/tasks/${taskId}/records`, {
            params: { limit: 20 }
          })
          setPreview(data)
        } catch { /* preview optional */ }
      } catch (err) {
        setError((err as Error).message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [taskId])

  const handleDownload = async () => {
    setDownloading(true)
    try { await downloadResults(taskId) } catch { /* ignore */ }
    finally { setDownloading(false) }
  }

  const handleDownloadLogs = async () => {
    setDownloadingLogs(true)
    try { await downloadLogs(taskId) } catch { /* ignore */ }
    finally { setDownloadingLogs(false) }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex items-center gap-3 text-slate-500">
          <div className="w-5 h-5 border-2 border-primary-400 border-t-transparent rounded-full animate-spin" />
          Загрузка результатов...
        </div>
      </div>
    )
  }

  if (error || !task) {
    return (
      <div className="text-center py-20">
        <p className="text-red-500 text-sm">{error ?? 'Задача не найдена'}</p>
        <button onClick={() => navigate('/tasks')} className="mt-4 text-primary-600 text-sm underline">
          Назад к списку задач
        </button>
      </div>
    )
  }

  const displayedRecords = showAll ? preview : preview.slice(0, 10)

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Заголовок */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Результаты</h1>
        <p className="text-slate-400 text-xs font-mono mt-0.5">{taskId}</p>
      </div>

      {/* ★ ГЛАВНАЯ КНОПКА СКАЧИВАНИЯ — крупная, на всю ширину */}
      <div className="flex flex-col sm:flex-row gap-3">
        <button
          onClick={handleDownload}
          disabled={downloading || !task.result_file}
          className="flex-1 flex items-center justify-center gap-3 px-6 py-4 bg-green-600 hover:bg-green-700 disabled:bg-slate-200 text-white disabled:text-slate-400 rounded-xl text-base font-bold transition-colors disabled:cursor-not-allowed shadow-lg hover:shadow-xl"
        >
          <Download className="w-6 h-6" />
          {downloading ? 'Загрузка файла...' : 'Скачать результат в Excel'}
        </button>
        {task.log_file && (
          <button
            onClick={handleDownloadLogs}
            disabled={downloadingLogs}
            className="flex items-center justify-center gap-2 px-5 py-4 border-2 border-slate-200 text-slate-600 hover:bg-slate-50 rounded-xl text-sm font-medium transition-colors disabled:opacity-50"
          >
            <FileText className="w-5 h-5" />
            {downloadingLogs ? 'Загрузка...' : 'Скачать логи'}
          </button>
        )}
      </div>

      {/* Статистика */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="card p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1.5">
            <Users className="w-3.5 h-3.5" />
            Найдено записей
          </div>
          <p className="text-2xl font-bold text-slate-900">{task.progress.contacts_found}</p>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1.5">
            <Globe className="w-3.5 h-3.5" />
            Обработано сайтов
          </div>
          <p className="text-2xl font-bold text-slate-900">
            {task.progress.processed_sites}
            <span className="text-sm font-normal text-slate-400"> / {task.progress.total_sites}</span>
          </p>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            Ошибок
          </div>
          <p className={`text-2xl font-bold ${task.progress.errors > 0 ? 'text-amber-600' : 'text-slate-900'}`}>
            {task.progress.errors}
          </p>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1.5">
            <Clock className="w-3.5 h-3.5" />
            Время парсинга
          </div>
          <p className="text-2xl font-bold text-slate-900">{formatDuration(task.progress.elapsed_seconds)}</p>
        </div>
      </div>

      {/* Предпросмотр записей */}
      {preview.length > 0 ? (
        <div className="card overflow-hidden">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between">
            <h2 className="font-semibold text-sm text-slate-700">
              Предпросмотр записей
              <span className="text-slate-400 font-normal ml-2">первые {Math.min(preview.length, showAll ? preview.length : 10)}</span>
            </h2>
            <FileSpreadsheet className="w-4 h-4 text-slate-400" />
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Организация</th>
                  <th>ФИО</th>
                  <th>Должность</th>
                  <th>Email</th>
                  <th>Телефон</th>
                  <th>ИНН</th>
                  <th>Сайт</th>
                </tr>
              </thead>
              <tbody>
                {displayedRecords.map((r, i) => (
                  <tr key={i}>
                    <td className="max-w-[180px]">
                      <span className="truncate block" title={r.company_name}>{r.company_name ?? '—'}</span>
                    </td>
                    <td className="whitespace-nowrap">{r.full_name ?? '—'}</td>
                    <td className="max-w-[160px]">
                      <span className="truncate block" title={r.position_raw}>{r.position_raw ?? '—'}</span>
                    </td>
                    <td>
                      {r.personal_email ? (
                        <a href={`mailto:${r.personal_email}`} className="text-primary-600 hover:underline text-xs">
                          {r.personal_email}
                        </a>
                      ) : r.company_email ? (
                        <a href={`mailto:${r.company_email}`} className="text-primary-600 hover:underline text-xs">
                          {r.company_email}
                        </a>
                      ) : '—'}
                    </td>
                    <td className="whitespace-nowrap font-mono text-xs">{r.phone ?? '—'}</td>
                    <td className="font-mono text-xs">{r.inn ?? '—'}</td>
                    <td>
                      {r.site_url ? (
                        <a
                          href={r.site_url.startsWith('http') ? r.site_url : `https://${r.site_url}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary-600 hover:underline flex items-center gap-1 text-xs"
                        >
                          <ExternalLink className="w-3 h-3" />
                          {(() => {
                            try {
                              return new URL(r.site_url.startsWith('http') ? r.site_url : `https://${r.site_url}`).hostname
                            } catch { return r.site_url }
                          })()}
                        </a>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {preview.length > 10 && (
            <button
              onClick={() => setShowAll(!showAll)}
              className="w-full py-3 text-sm text-primary-600 hover:bg-primary-50 flex items-center justify-center gap-1.5 border-t border-slate-100 transition-colors"
            >
              {showAll ? (
                <><ChevronUp className="w-4 h-4" /> Свернуть</>
              ) : (
                <><ChevronDown className="w-4 h-4" /> Показать ещё {preview.length - 10}</>
              )}
            </button>
          )}
        </div>
      ) : (
        <div className="card p-12 text-center">
          <Users className="w-8 h-8 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Предпросмотр недоступен</p>
          <p className="text-slate-300 text-xs mt-1">Скачайте Excel файл для просмотра результатов</p>
        </div>
      )}

      {/* ★ ПОВТОРНАЯ КНОПКА СКАЧИВАНИЯ ВНИЗУ */}
      <div className="flex flex-col sm:flex-row gap-3">
        <button
          onClick={handleDownload}
          disabled={downloading || !task.result_file}
          className="flex-1 flex items-center justify-center gap-3 px-6 py-4 bg-green-600 hover:bg-green-700 disabled:bg-slate-200 text-white disabled:text-slate-400 rounded-xl text-base font-bold transition-colors disabled:cursor-not-allowed shadow-lg hover:shadow-xl"
        >
          <Download className="w-6 h-6" />
          {downloading ? 'Загрузка файла...' : 'Скачать результат в Excel'}
        </button>
      </div>

      {/* Навигация */}
      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-semibold transition-colors"
        >
          Новая задача
        </button>
        <button
          onClick={() => navigate('/tasks')}
          className="px-4 py-2 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-medium transition-colors"
        >
          Все задачи
        </button>
      </div>
    </div>
  )
}
