import { useState, useCallback, DragEvent, ChangeEvent } from 'react'
import {
  Upload, ShieldCheck, Trash2, AlertCircle, CheckCircle2,
  Loader2, X, RefreshCw
} from 'lucide-react'
import { uploadBlacklist, getBlacklist, removeFromBlacklist } from '../api'

interface BlacklistEntry {
  domain: string
  reason?: string
  added_at: string
}

export default function BlacklistUpload() {
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<{ added: number; total: number } | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [entries, setEntries] = useState<BlacklistEntry[]>([])
  const [loadingEntries, setLoadingEntries] = useState(false)
  const [removingDomain, setRemovingDomain] = useState<string | null>(null)

  const loadEntries = useCallback(async () => {
    setLoadingEntries(true)
    try {
      const data = await getBlacklist()
      setEntries(data.entries)
    } catch { /* ignore */ }
    finally { setLoadingEntries(false) }
  }, [])

  useState(() => { loadEntries() })

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
      await loadEntries()
    } catch (err) {
      setUploadError((err as Error).message)
    } finally {
      setUploading(false)
    }
  }

  const handleRemove = async (domain: string) => {
    setRemovingDomain(domain)
    try {
      await removeFromBlacklist(domain)
      setEntries(prev => prev.filter(e => e.domain !== domain))
    } catch { /* ignore */ }
    finally { setRemovingDomain(null) }
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
            Добавлено {uploadResult.added} доменов. Всего в базе: {uploadResult.total}
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

      <div className="card overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-700">
            Текущий чёрный список
            {entries.length > 0 && (
              <span className="ml-2 text-xs font-normal text-slate-400">({entries.length} доменов)</span>
            )}
          </h2>
          <button
            onClick={loadEntries}
            disabled={loadingEntries}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
            title="Обновить"
          >
            <RefreshCw className={`w-4 h-4 ${loadingEntries ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {loadingEntries ? (
          <div className="py-8 flex justify-center">
            <Loader2 className="w-5 h-5 text-primary-400 animate-spin" />
          </div>
        ) : entries.length === 0 ? (
          <div className="py-12 text-center">
            <ShieldCheck className="w-8 h-8 text-slate-200 mx-auto mb-2" />
            <p className="text-slate-400 text-sm">Чёрный список пуст</p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100 max-h-96 overflow-y-auto">
            {entries.map((entry) => (
              <li key={entry.domain} className="flex items-center gap-3 px-4 py-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-mono text-slate-700 truncate">{entry.domain}</p>
                  {entry.reason && (
                    <p className="text-xs text-slate-400 mt-0.5">{entry.reason}</p>
                  )}
                </div>
                <span className="text-xs text-slate-300 flex-shrink-0">
                  {new Date(entry.added_at).toLocaleDateString('ru-RU')}
                </span>
                <button
                  onClick={() => handleRemove(entry.domain)}
                  disabled={removingDomain === entry.domain}
                  className="p-1.5 text-slate-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors flex-shrink-0"
                  title="Удалить из чёрного списка"
                >
                  {removingDomain === entry.domain
                    ? <Loader2 className="w-4 h-4 animate-spin" />
                    : <Trash2 className="w-4 h-4" />
                  }
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
