import { useState, useEffect, useRef } from 'react'
import {
  ShieldBan,
  Upload,
  Plus,
  Trash2,
  Loader2,
  Globe,
  Mail,
  Hash,
  Download,
  AlertCircle,
  CheckCircle2,
  X,
} from 'lucide-react'
import { getBlacklist, uploadBlacklist, addBlacklistEntry, removeBlacklistEntry } from '../api'
import type { BlacklistData, BlacklistEntry } from '../types'

export default function BlacklistUpload() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [data, setData] = useState<BlacklistData | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Add entry form
  const [newValue, setNewValue] = useState('')
  const [newType, setNewType] = useState<'domain' | 'email' | 'inn'>('domain')
  const [adding, setAdding] = useState(false)

  const load = async () => {
    try {
      const d = await getBlacklist()
      setData(d)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    setSuccess(null)
    try {
      const result = await uploadBlacklist(file)
      setSuccess(`Добавлено ${result.added} записей. Всего: ${result.total}`)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки файла')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleAddEntry = async () => {
    if (!newValue.trim()) return
    setAdding(true)
    setError(null)
    try {
      await addBlacklistEntry(newValue.trim(), newType)
      setNewValue('')
      setSuccess('Запись добавлена')
      await load()
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка добавления')
    } finally {
      setAdding(false)
    }
  }

  const handleRemoveEntry = async (id: string) => {
    try {
      await removeBlacklistEntry(id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка удаления')
    }
  }

  const handleExport = () => {
    if (!data?.entries?.length) return
    const text = data.entries.map(e => `${e.type}\t${e.value}`).join('\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'blacklist_export.txt'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  const TypeIcon = ({ type }: { type: string }) => {
    if (type === 'domain') return <Globe className="w-3.5 h-3.5 text-blue-400" />
    if (type === 'email') return <Mail className="w-3.5 h-3.5 text-violet-400" />
    return <Hash className="w-3.5 h-3.5 text-amber-400" />
  }

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <ShieldBan className="w-5 h-5 text-red-400" />
            Чёрный список
          </h1>
          <p className="text-sm text-slate-400 mt-1">Домены, email и ИНН, исключённые из обработки</p>
        </div>
        {data?.entries && data.entries.length > 0 && (
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-slate-400 border border-slate-700 hover:border-slate-600 hover:text-slate-300 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            Экспорт
          </button>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="glass-card p-4 text-center">
          <Globe className="w-5 h-5 text-blue-400 mx-auto mb-2" />
          <p className="text-xl font-bold text-white">{data?.domains ?? 0}</p>
          <p className="text-xs text-slate-400 mt-1">Домены</p>
        </div>
        <div className="glass-card p-4 text-center">
          <Mail className="w-5 h-5 text-violet-400 mx-auto mb-2" />
          <p className="text-xl font-bold text-white">{data?.emails ?? 0}</p>
          <p className="text-xs text-slate-400 mt-1">Email</p>
        </div>
        <div className="glass-card p-4 text-center">
          <Hash className="w-5 h-5 text-amber-400 mx-auto mb-2" />
          <p className="text-xl font-bold text-white">{data?.inns ?? 0}</p>
          <p className="text-xs text-slate-400 mt-1">ИНН</p>
        </div>
      </div>

      {/* Upload file */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">Загрузить файл</h3>
        <div
          onClick={() => fileInputRef.current?.click()}
          className="drop-zone flex items-center justify-center gap-3 py-6 cursor-pointer"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.xlsx,.xls,.csv"
            onChange={handleUpload}
            className="hidden"
          />
          {uploading ? (
            <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
          ) : (
            <Upload className="w-5 h-5 text-slate-500" />
          )}
          <span className="text-sm text-slate-400">
            {uploading ? 'Загрузка...' : 'Нажмите или перетащите файл (.txt, .xlsx, .csv)'}
          </span>
        </div>
      </div>

      {/* Add entry */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">Добавить запись</h3>
        <div className="flex gap-3">
          <select
            value={newType}
            onChange={(e) => setNewType(e.target.value as 'domain' | 'email' | 'inn')}
            className="glass-input w-32 text-sm"
          >
            <option value="domain">Домен</option>
            <option value="email">Email</option>
            <option value="inn">ИНН</option>
          </select>
          <input
            type="text"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddEntry()}
            placeholder={
              newType === 'domain' ? 'example.com' :
              newType === 'email' ? 'user@example.com' :
              '1234567890'
            }
            className="glass-input flex-1"
          />
          <button
            onClick={handleAddEntry}
            disabled={adding || !newValue.trim()}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              adding || !newValue.trim()
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                : 'bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20'
            }`}
          >
            {adding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
            Добавить
          </button>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <p className="text-sm text-red-400 flex-1">{error}</p>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {success && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <p className="text-sm text-emerald-400 flex-1">{success}</p>
          <button onClick={() => setSuccess(null)} className="text-emerald-400 hover:text-emerald-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Entries table */}
      {data?.entries && data.entries.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="dark-table">
              <thead>
                <tr>
                  <th className="w-24">Тип</th>
                  <th>Значение</th>
                  <th className="w-40">Добавлено</th>
                  <th className="w-16">Действия</th>
                </tr>
              </thead>
              <tbody>
                {data.entries.map((entry: BlacklistEntry) => (
                  <tr key={entry.id}>
                    <td>
                      <div className="flex items-center gap-1.5">
                        <TypeIcon type={entry.type} />
                        <span className="text-xs capitalize">{entry.type}</span>
                      </div>
                    </td>
                    <td>
                      <span className="text-xs font-mono text-slate-200">{entry.value}</span>
                    </td>
                    <td className="text-xs">
                      {new Date(entry.added_at).toLocaleString('ru-RU', {
                        day: '2-digit', month: '2-digit', year: '2-digit',
                        hour: '2-digit', minute: '2-digit',
                      })}
                    </td>
                    <td>
                      <button
                        onClick={() => handleRemoveEntry(entry.id)}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                        title="Удалить"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
        </div>
      )}
    </div>
  )
}
