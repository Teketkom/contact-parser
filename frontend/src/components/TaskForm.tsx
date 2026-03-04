import { useState, useRef, useCallback, DragEvent, ChangeEvent } from 'react'
import {
  Upload, FileSpreadsheet, X, ChevronDown, AlertCircle, Loader2, Play
} from 'lucide-react'
import { createTask, previewFile } from '../api'
import type { TaskMode, UploadFileInfo } from '../types'

interface TaskFormProps {
  onTaskCreated: (taskId: string) => void
}

const ACCEPTED_TYPES = [
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-excel',
  'text/csv',
  '.xlsx',
  '.xls',
  '.csv',
]

const formatBytes = (bytes: number) => {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`
}

export default function TaskForm({ onTaskCreated }: TaskFormProps) {
  const [mode, setMode] = useState<TaskMode>(1)
  const [file, setFile] = useState<File | null>(null)
  const [fileInfo, setFileInfo] = useState<UploadFileInfo | null>(null)
  const [filePreviewLoading, setFilePreviewLoading] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)
  const [positions, setPositions] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(async (f: File) => {
    const ext = f.name.split('.').pop()?.toLowerCase()
    if (!ext || !['xlsx', 'xls', 'csv'].includes(ext)) {
      setFileError('Допустимые форматы: .xlsx, .xls, .csv')
      return
    }
    setFile(f)
    setFileError(null)
    setFileInfo(null)
    setFilePreviewLoading(true)
    try {
      const info = await previewFile(f)
      setFileInfo(info)
    } catch {
      setFileInfo({ filename: f.name, size_bytes: f.size, rows_count: 0, preview_urls: [] })
    } finally {
      setFilePreviewLoading(false)
    }
  }, [])

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }, [handleFile])

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleInputChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) handleFile(f)
  }, [handleFile])

  const handleRemoveFile = useCallback(() => {
    setFile(null)
    setFileInfo(null)
    setFileError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [])

  const handleSubmit = async () => {
    if (!file) {
      setSubmitError('Пожалуйста, загрузите файл со списком сайтов')
      return
    }
    if (mode === 1 && !positions.trim()) {
      setSubmitError('Для режима 1 необходимо указать целевые должности')
      return
    }
    setSubmitError(null)
    setIsSubmitting(true)
    try {
      const targetPositions = mode === 1
        ? positions.split(',').map(p => p.trim()).filter(Boolean)
        : undefined
      const res = await createTask(file, mode, targetPositions)
      onTaskCreated(res.task_id)
    } catch (err) {
      setSubmitError((err as Error).message)
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Mode selector */}
      <div className="card p-5">
        <label className="block text-sm font-semibold text-slate-700 mb-3">
          Режим работы
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {([1, 2] as TaskMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`relative p-4 rounded-xl border-2 text-left transition-all ${
                mode === m
                  ? 'border-primary-600 bg-primary-50'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-start gap-3">
                <div className={`w-4 h-4 mt-0.5 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
                  mode === m ? 'border-primary-600' : 'border-slate-300'
                }`}>
                  {mode === m && (
                    <div className="w-2 h-2 rounded-full bg-primary-600" />
                  )}
                </div>
                <div>
                  <p className={`font-semibold text-sm ${mode === m ? 'text-primary-700' : 'text-slate-700'}`}>
                    Режим {m}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                    {m === 1
                      ? 'Список сайтов + целевые должности — извлекать только нужные позиции'
                      : 'Список сайтов + все должности — извлекать всех найденных сотрудников'}
                  </p>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* File upload */}
      <div className="card p-5">
        <label className="block text-sm font-semibold text-slate-700 mb-3">
          Файл со списком сайтов
          <span className="text-xs font-normal text-slate-400 ml-2">.xlsx, .xls, .csv</span>
        </label>

        {!file ? (
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
            className={`
              border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
              ${isDragging
                ? 'border-primary-500 bg-primary-50'
                : 'border-slate-200 bg-slate-50 hover:border-primary-300 hover:bg-primary-50/30'}
            `}
          >
            <Upload className={`w-8 h-8 mx-auto mb-3 ${isDragging ? 'text-primary-500' : 'text-slate-400'}`} />
            <p className="text-sm font-medium text-slate-700 mb-1">
              {isDragging ? 'Отпустите файл' : 'Перетащите файл или нажмите для выбора'}
            </p>
            <p className="text-xs text-slate-400">
              Поддерживаются: Excel (.xlsx, .xls) и CSV файлы
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              className="hidden"
              onChange={handleInputChange}
            />
          </div>
        ) : (
          <div className="border border-slate-200 rounded-xl p-4 bg-slate-50">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-50 border border-green-200 flex items-center justify-center flex-shrink-0">
                <FileSpreadsheet className="w-5 h-5 text-green-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800 truncate">{file.name}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-slate-400">{formatBytes(file.size)}</span>
                  {filePreviewLoading && (
                    <span className="text-xs text-primary-500 flex items-center gap-1">
                      <Loader2 className="w-3 h-3 animate-spin" /> Проверка...
                    </span>
                  )}
                  {fileInfo && fileInfo.rows_count > 0 && (
                    <span className="text-xs text-green-600">{fileInfo.rows_count} строк</span>
                  )}
                </div>
                {fileInfo?.preview_urls && fileInfo.preview_urls.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {fileInfo.preview_urls.slice(0, 3).map((url, i) => (
                      <span key={i} className="text-xs bg-white border border-slate-200 rounded px-2 py-0.5 text-slate-500 font-mono truncate max-w-[200px]">
                        {url}
                      </span>
                    ))}
                    {fileInfo.preview_urls.length > 3 && (
                      <span className="text-xs text-slate-400">+{fileInfo.preview_urls.length - 3} ещё</span>
                    )}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={handleRemoveFile}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {fileError && (
          <div className="mt-2 flex items-center gap-1.5 text-red-500 text-xs">
            <AlertCircle className="w-3.5 h-3.5" />
            {fileError}
          </div>
        )}
      </div>

      {/* Target positions */}
      {mode === 1 && (
        <div className="card p-5 animate-slide-up">
          <label className="block text-sm font-semibold text-slate-700 mb-1.5" htmlFor="positions">
            Целевые должности
          </label>
          <p className="text-xs text-slate-400 mb-3">
            Введите должности через запятую. Используется нечёткое сопоставление.
          </p>
          <textarea
            id="positions"
            value={positions}
            onChange={(e) => setPositions(e.target.value)}
            rows={3}
            placeholder="Директор, Генеральный директор, CEO, Руководитель, Начальник отдела"
            className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 bg-white placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 resize-none transition-colors"
          />
          {positions && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {positions.split(',').map(p => p.trim()).filter(Boolean).map((p, i) => (
                <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary-50 text-primary-700 text-xs rounded-full border border-primary-100">
                  {p}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Submit error */}
      {submitError && (
        <div className="flex items-start gap-2.5 p-3.5 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{submitError}</span>
        </div>
      )}

      {/* Submit */}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={isSubmitting || !file}
        className="
          w-full flex items-center justify-center gap-2 px-5 py-3 
          bg-primary-600 hover:bg-primary-700 disabled:bg-slate-200 disabled:cursor-not-allowed
          text-white disabled:text-slate-400 font-semibold text-sm rounded-xl
          transition-all shadow-sm hover:shadow-md disabled:shadow-none
        "
      >
        {isSubmitting ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Создание задачи...
          </>
        ) : (
          <>
            <Play className="w-4 h-4" />
            Начать парсинг
          </>
        )}
      </button>
    </div>
  )
}
