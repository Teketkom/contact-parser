import { useState, useCallback, useEffect, DragEvent, ChangeEvent } from 'react'
import {
  Upload, ShieldCheck, AlertCircle, CheckCircle2,
  Loader2, X, RefreshCw
} from 'lucide-react'
import { uploadBlacklist, getBlacklist } from '../api'

interface BlacklistStats {
  domains: number
  emails: number
  inns: number
  total: number
}

export default function BlacklistUpload() {
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<{ added: number; total: number } | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [stats, setStats] = useState<BlacklistStats | null>(null)
  const [loadingStats, setLoadingStats] = useState(false)

  const loadStats = useCallback(async () => {
    setLoadingStats(true)
    try {
      const data = await getBlacklist()
      setStats(data)
    } catch { /* ignore */ }
    finally { setLoadingStats(false) }
  }, [])

  useEffect(() => { loadStats() }, [loadStats])

  const handleFile = useCallback((f: File) => {
    const ext = f.name.split('.').pop()?.toLowerCase()
    if (!ext || !['txt', 'xlsx', 'xls', 'csv'].includes(ext)) {
      setUploadError('Допустимые форматы: .txt, .xlsx, .xls, .csv')
      return
    }
    setFile(f)
    setUploadError(null)
    setUploadResult(null)
  }, [])

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }, [handleFile])

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setUploadError(null)
    try {
      const res = await uploadBlacklist(file)
      setUploadResult({ added: res.added, total: res.total })
      setFile(null)
      await loadStats()
    } catch (err) {
      setUploadError((err as Error).message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-slate-500" />
          Загрузить список доменов для блокировки
        </h2>

        {!file ? (
          <div
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
            onDragLeave={(e) => { e.preventDefault(); setIsDragging(false) }}
            onClick={() => document.getElementById('bl-input')?.click()}
            className={`
              border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
              ${isDragging
                ? 'border-primary-500 bg-primary-50'
                : 'border-slate-200 bg-slate-50 hover:border-primary-300 hover:bg-primary-50/30'}
            `}
          >
            <Upload className={`w-7 h-7 mx-auto mb-2 ${isDragging ? 'text-primary-500' : 'text-slate-400'}`} />
            <p className="text-sm font-medium text-slate-700">Перетащите файл или нажмите для выбора</p>
            <p className="text-xs text-slate-400 mt-1">
              Форматы: .txt (один домен на строку), .xlsx, .xls, .csv
            </p>
            <input
              id="bl-input"
              type="file"
              accept=".txt,.xlsx,.xls,.csv"
              className="hidden"
              onChange={(e: ChangeEvent<HTMLInputElement>) => {
                const f = e.target.files?.[0]
                if (f) handleFile(f)
              }}
            />
          </div>
        ) : (
          <div className="border border-slate-200 rounded-xl p-4 bg-slate-50 flex items-center gap-3">
            <div className="flex-1">
              <p className="text-sm font-medium text-slate-800">{file.name}</p>
              <p className="text-xs text-slate-400">{(file.size / 1024).toFixed(1)} КБ</p>
            </div>
            <button
              onClick={() => setFile(null)}
              className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {uploadError && (
          <div className="mt-3 flex items-center gap-2 text-red-500 text-xs">
            <AlertCircle className="w-3.5 h-3.5" />
            {uploadError}
          </div>
        )}

        {uploadResult && (
          <div className="mt-3 flex items-center gap-2 text-green-600 text-sm">
            <CheckCircle2 className="w-4 h-4" />
            Добавлено {uploadResult.added} записей. Всего в базе: {uploadResult.total}
          </div>
        )}

        {file && (
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary-600 hover:bg-primary-700 disabled:bg-slate-200 text-white disabled:text-slate-400 rounded-lg text-sm font-semibold transition-colors"
          >
            {uploading ? (
              <><Loader2 className="w-4 h-4 animate-spin" />Загрузка...</>
            ) : (
              <><Upload className="w-4 h-4" />Загрузить в чёрный список</>
            )}
          </button>
        )}
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-slate-500" />
            Статистика чёрного списка
          </h2>
          <button
            onClick={loadStats}
            disabled={loadingStats}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
            title="Обновить"
          >
            <RefreshCw className={`w-4 h-4 ${loadingStats ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {stats ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 bg-slate-50 rounded-lg text-center">
              <p className="text-2xl font-bold text-slate-900">{stats.total}</p>
              <p className="text-xs text-slate-400 mt-0.5">Всего записей</p>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg text-center">
              <p className="text-2xl font-bold text-slate-900">{stats.domains}</p>
              <p className="text-xs text-slate-400 mt-0.5">Доменов</p>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg text-center">
              <p className="text-2xl font-bold text-slate-900">{stats.emails}</p>
              <p className="text-xs text-slate-400 mt-0.5">Email</p>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg text-center">
              <p className="text-2xl font-bold text-slate-900">{stats.inns}</p>
              <p className="text-xs text-slate-400 mt-0.5">ИНН</p>
            </div>
          </div>
        ) : loadingStats ? (
          <div className="py-8 flex justify-center">
            <Loader2 className="w-5 h-5 text-primary-400 animate-spin" />
          </div>
        ) : (
          <div className="py-8 text-center">
            <ShieldCheck className="w-8 h-8 text-slate-200 mx-auto mb-2" />
            <p className="text-slate-400 text-sm">Чёрный список пуст</p>
          </div>
        )}
      </div>
    </div>
  )
}
