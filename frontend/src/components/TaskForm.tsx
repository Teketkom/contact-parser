import { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload,
  FileSpreadsheet,
  Globe,
  Play,
  Loader2,
  X,
  Sparkles,
  SlidersHorizontal,
  AlertCircle,
  CheckCircle2,
  Link2,
} from 'lucide-react'
import { createTask, createTaskFromUrl, previewFile } from '../api'
import type { UploadFileInfo } from '../types'

export default function TaskForm() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<UploadFileInfo | null>(null)
  const [urlInput, setUrlInput] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<'file' | 'url'>('file')

  // Settings
  const [maxPages, setMaxPages] = useState(50)
  const [llmNormalize, setLlmNormalize] = useState(true)
  const [showSettings, setShowSettings] = useState(false)

  // Drag & drop handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) {
      await handleFileSelect(droppedFile)
    }
  }, [])

  const handleFileSelect = async (selectedFile: File) => {
    setFile(selectedFile)
    setError(null)
    setPreviewLoading(true)
    try {
      const info = await previewFile(selectedFile)
      setPreview(info)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка при анализе файла')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) handleFileSelect(selectedFile)
  }

  const removeFile = () => {
    setFile(null)
    setPreview(null)
    setError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleSubmit = async () => {
    setError(null)
    setLoading(true)
    try {
      let task
      if (mode === 'url' && urlInput.trim()) {
        task = await createTaskFromUrl(urlInput.trim(), { max_pages: maxPages, llm_normalize: llmNormalize })
      } else if (file) {
        task = await createTask(file, { max_pages: maxPages, llm_normalize: llmNormalize })
      } else {
        setError('Загрузите файл или введите URL')
        setLoading(false)
        return
      }
      navigate(`/tasks/${task.task_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка при создании задачи')
    } finally {
      setLoading(false)
    }
  }

  const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} Б`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`
    return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
  }

  return (
    <div className="animate-fade-in space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold text-white">Новая задача</h1>
        <p className="text-sm text-slate-400 mt-1">Загрузите файл или введите URL для парсинга контактов</p>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setMode('file')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            mode === 'file'
              ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30'
              : 'text-slate-400 hover:text-slate-300 border border-transparent hover:bg-slate-800/40'
          }`}
        >
          <FileSpreadsheet className="w-4 h-4" />
          Файл со списком
        </button>
        <button
          onClick={() => setMode('url')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            mode === 'url'
              ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30'
              : 'text-slate-400 hover:text-slate-300 border border-transparent hover:bg-slate-800/40'
          }`}
        >
          <Globe className="w-4 h-4" />
          Быстрый URL
        </button>
      </div>

      {/* File upload section */}
      {mode === 'file' && (
        <div className="glass-card p-6">
          {!file ? (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`drop-zone ${isDragging ? 'drop-zone-active' : ''}`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls,.csv,.txt"
                onChange={handleFileInputChange}
                className="hidden"
              />
              <Upload className={`w-10 h-10 mx-auto mb-3 ${isDragging ? 'text-blue-400' : 'text-slate-500'}`} />
              <p className="text-sm text-slate-300 mb-1">
                Перетащите файл сюда или{' '}
                <span className="text-blue-400 font-medium">нажмите для выбора</span>
              </p>
              <p className="text-xs text-slate-500">
                Поддерживаются: .xlsx, .xls, .csv, .txt
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* File info card */}
              <div className="flex items-start gap-4 p-4 rounded-lg bg-slate-800/40">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center shrink-0">
                  <FileSpreadsheet className="w-5 h-5 text-emerald-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">{file.name}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{formatBytes(file.size)}</p>
                  {previewLoading && (
                    <div className="flex items-center gap-2 mt-2">
                      <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />
                      <span className="text-xs text-slate-400">Анализ файла...</span>
                    </div>
                  )}
                  {preview && (
                    <div className="flex items-center gap-4 mt-2">
                      <span className="text-xs text-slate-400">
                        <CheckCircle2 className="w-3.5 h-3.5 inline mr-1 text-emerald-400" />
                        {preview.rows_count} сайтов
                      </span>
                    </div>
                  )}
                </div>
                <button
                  onClick={removeFile}
                  className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-700/50 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* URL Preview list */}
              {preview && preview.preview_urls.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-400 mb-2">Предпросмотр URL:</p>
                  <div className="space-y-1 max-h-32 overflow-y-auto no-scrollbar">
                    {preview.preview_urls.slice(0, 10).map((url, i) => (
                      <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-slate-800/30">
                        <Link2 className="w-3 h-3 text-slate-500 shrink-0" />
                        <span className="text-xs text-slate-400 truncate">{url}</span>
                      </div>
                    ))}
                    {preview.preview_urls.length > 10 && (
                      <p className="text-[10px] text-slate-500 px-3 py-1">
                        ...и ещё {preview.preview_urls.length - 10}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* URL input section */}
      {mode === 'url' && (
        <div className="glass-card p-6">
          <label className="block text-xs font-medium text-slate-400 mb-2">URL сайта для парсинга</label>
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="url"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://example.com"
                className="glass-input w-full pl-10"
              />
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Введите URL сайта для быстрого извлечения контактов
          </p>
        </div>
      )}

      {/* AI Suggestions placeholder */}
      {file && preview && (
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-violet-400" />
            <h3 className="text-sm font-semibold text-slate-300">AI: Похожие компании</h3>
          </div>
          <p className="text-xs text-slate-500">
            На основе загруженного списка AI может предложить похожие компании для расширения выборки.
            Эта функция доступна при подключённом LLM сервере.
          </p>
          <button className="mt-3 px-3 py-1.5 rounded-lg text-xs font-medium bg-violet-500/10 text-violet-400 border border-violet-500/20 hover:bg-violet-500/20 transition-colors">
            Получить рекомендации
          </button>
        </div>
      )}

      {/* Settings panel */}
      <div className="glass-card overflow-hidden">
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="w-full flex items-center justify-between px-5 py-3.5 text-left hover:bg-slate-800/30 transition-colors"
        >
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-4 h-4 text-slate-400" />
            <span className="text-sm font-medium text-slate-300">Настройки парсинга</span>
          </div>
          <span className={`text-xs text-slate-500 transition-transform ${showSettings ? 'rotate-180' : ''}`}>▼</span>
        </button>

        {showSettings && (
          <div className="px-5 pb-5 space-y-5 border-t border-slate-800/50 pt-4">
            {/* Max pages slider */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-medium text-slate-400">
                  Макс. страниц на сайт
                </label>
                <span className="text-xs font-bold text-blue-400">{maxPages}</span>
              </div>
              <input
                type="range"
                min="1"
                max="200"
                value={maxPages}
                onChange={(e) => setMaxPages(Number(e.target.value))}
                className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer
                  [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                  [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:cursor-pointer
                  [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-blue-500/30"
              />
              <div className="flex justify-between mt-1">
                <span className="text-[10px] text-slate-600">1</span>
                <span className="text-[10px] text-slate-600">200</span>
              </div>
            </div>

            {/* LLM Normalization toggle */}
            <div className="flex items-center justify-between">
              <div>
                <label className="text-xs font-medium text-slate-400">LLM нормализация</label>
                <p className="text-[10px] text-slate-500 mt-0.5">
                  Использовать AI для нормализации должностей
                </p>
              </div>
              <button
                onClick={() => setLlmNormalize(!llmNormalize)}
                className={`relative w-10 h-5 rounded-full transition-colors ${
                  llmNormalize ? 'bg-blue-500' : 'bg-slate-700'
                }`}
              >
                <span
                  className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                    llmNormalize ? 'left-[22px]' : 'left-0.5'
                  }`}
                />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Submit button */}
      <button
        onClick={handleSubmit}
        disabled={loading || (mode === 'file' && !file) || (mode === 'url' && !urlInput.trim())}
        className={`
          w-full flex items-center justify-center gap-2.5 py-3.5 rounded-xl text-sm font-semibold
          transition-all duration-200
          ${loading || (mode === 'file' && !file) || (mode === 'url' && !urlInput.trim())
            ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
            : 'bg-gradient-to-r from-emerald-500 to-green-500 text-white shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40 hover:scale-[1.01]'
          }
        `}
      >
        {loading ? (
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
