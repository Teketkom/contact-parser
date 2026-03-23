import { useState, useRef, useCallback, DragEvent, ChangeEvent } from 'react'
import {
  Upload, FileSpreadsheet, X, AlertCircle, Loader2, Play, Sparkles
} from 'lucide-react'
import { createTask, previewFile } from '../api'
import type { UploadFileInfo } from '../types'

interface TaskFormProps {
  onTaskCreated: (taskId: string) => void
}


const formatBytes = (bytes: number) => {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`
}

export default function TaskForm({ onTaskCreated }: TaskFormProps) {
  const [file, setFile] = useState<File | null>(null)
  const [fileInfo, setFileInfo] = useState<UploadFileInfo | null>(null)
  const [filePreviewLoading, setFilePreviewLoading] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(async (f: File) => {
    const ext = f.name.split('.').pop()?.toLowerCase()
    if (!ext || !['xlsx', 'xls', 'csv', 'txt'].includes(ext)) {
      setFileError('Допустимые форматы: .xlsx, .xls, .csv, .txt')
      setFile(null)
      return
    }
    // Устанавливаем файл СРАЗУ — кнопка станет активной
    setFile(f)
    setFileError(null)
    setFileInfo(null)
    setSubmitError(null)

    // Превью загружаем асинхронно — не блокирует кнопку
    setFilePreviewLoading(true)
    try {
      const info = await previewFile(f)
      setFileInfo(info)
    } catch {
      // Превью недоступно — не критично, файл всё равно установлен
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
    setSubmitError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [])

  const handleSubmit = async () => {
    if (!file) {
      setSubmitError('Пожалуйста, загрузите файл со списком сайтов')
      return
    }
    setSubmitError(null)
    setIsSubmitting(true)
    try {
      const res = await createTask(file)
      onTaskCreated(res.task_id)
    } catch (err) {
      setSubmitError((err as Error).message)
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* File upload */}
      <div className="card p-5">
        <label className="block text-sm font-semibold text-slate-700 mb-3">
          Файл со списком сайтов
          <span className="text-xs font-normal text-slate-400 ml-2">.xlsx, .xls, .csv, .txt</span>
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
              Поддерживаются: Excel (.xlsx, .xls), CSV и TXT файлы
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv,.txt"
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
                    <span className="text-xs text-green-600">
                      {fileInfo.rows_count} {fileInfo.rows_count === 1 ? 'сайт' : fileInfo.rows_count < 5 ? 'сайта' : 'сайтов'}
                    </span>
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

      {/* AI info banner */}
      <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl">
        <Sparkles className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-blue-800">Извлечение с помощью ИИ</p>
          <p className="text-xs text-blue-600 mt-0.5">
            Система автоматически извлечёт всех сотрудников с указанных сайтов используя ИИ
          </p>
        </div>
      </div>

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
          bg-green-600 hover:bg-green-700 disabled:bg-slate-200 disabled:cursor-not-allowed
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
