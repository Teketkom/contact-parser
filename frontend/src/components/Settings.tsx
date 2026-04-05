import { useState, useEffect } from 'react'
import {
  Settings as SettingsIcon,
  Brain,
  Globe,
  Server,
  Save,
  Loader2,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Info,
} from 'lucide-react'
import { getSettings, updateSettings, getSystemStatus } from '../api'
import type { AppSettings, SystemStatus } from '../types'

export default function Settings() {
  const [settings, setSettings] = useState<AppSettings>({
    llm_model: '',
    llm_api_url: '',
    llm_api_key: '',
    llm_timeout: 30,
    max_pages_per_site: 50,
    concurrent_browsers: 3,
    request_delay: 1000,
  })
  const [sysStatus, setSysStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        const [s, sys] = await Promise.all([getSettings(), getSystemStatus()])
        setSettings(s)
        setSysStatus(sys)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Ошибка загрузки настроек')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    setSuccess(false)
    try {
      const updated = await updateSettings(settings)
      setSettings(updated)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    setSettings({
      llm_model: '',
      llm_api_url: '',
      llm_api_key: '',
      llm_timeout: 30,
      max_pages_per_site: 50,
      concurrent_browsers: 3,
      request_delay: 1000,
    })
  }

  const formatUptime = (seconds: number): string => {
    const d = Math.floor(seconds / 86400)
    const h = Math.floor((seconds % 86400) / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    if (d > 0) return `${d}д ${h}ч ${m}м`
    if (h > 0) return `${h}ч ${m}м`
    return `${m}м`
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    )
  }

  return (
    <div className="animate-fade-in space-y-6 max-w-2xl">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-slate-400" />
          Настройки
        </h1>
        <p className="text-sm text-slate-400 mt-1">Конфигурация LLM, парсера и системы</p>
      </div>

      {/* LLM Configuration */}
      <div className="glass-card p-5">
        <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2 mb-4">
          <Brain className="w-4 h-4 text-violet-400" />
          Конфигурация LLM
        </h2>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">Модель</label>
            <input
              type="text"
              value={settings.llm_model}
              onChange={(e) => setSettings({ ...settings, llm_model: e.target.value })}
              placeholder="Например: llama-3.1-sonar-large-128k-online"
              className="glass-input w-full"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">API URL</label>
            <div className="relative">
              <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="url"
                value={settings.llm_api_url}
                onChange={(e) => setSettings({ ...settings, llm_api_url: e.target.value })}
                placeholder="https://api.perplexity.ai"
                className="glass-input w-full pl-10"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">API Key</label>
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={settings.llm_api_key}
                onChange={(e) => setSettings({ ...settings, llm_api_key: e.target.value })}
                placeholder="pplx-..."
                className="glass-input w-full pr-10"
              />
              <button
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
              >
                {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-slate-400">Таймаут (сек)</label>
              <span className="text-xs font-bold text-blue-400">{settings.llm_timeout}</span>
            </div>
            <input
              type="range"
              min="5"
              max="120"
              value={settings.llm_timeout}
              onChange={(e) => setSettings({ ...settings, llm_timeout: Number(e.target.value) })}
              className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:cursor-pointer"
            />
          </div>
        </div>
      </div>

      {/* Parser Configuration */}
      <div className="glass-card p-5">
        <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2 mb-4">
          <Globe className="w-4 h-4 text-cyan-400" />
          Настройки парсера
        </h2>
        <div className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-slate-400">Макс. страниц на сайт</label>
              <span className="text-xs font-bold text-blue-400">{settings.max_pages_per_site}</span>
            </div>
            <input
              type="range"
              min="1"
              max="500"
              value={settings.max_pages_per_site}
              onChange={(e) => setSettings({ ...settings, max_pages_per_site: Number(e.target.value) })}
              className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:cursor-pointer"
            />
          </div>
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-slate-400">Параллельных браузеров</label>
              <span className="text-xs font-bold text-blue-400">{settings.concurrent_browsers}</span>
            </div>
            <input
              type="range"
              min="1"
              max="10"
              value={settings.concurrent_browsers}
              onChange={(e) => setSettings({ ...settings, concurrent_browsers: Number(e.target.value) })}
              className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:cursor-pointer"
            />
          </div>
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-slate-400">Задержка между запросами (мс)</label>
              <span className="text-xs font-bold text-blue-400">{settings.request_delay}</span>
            </div>
            <input
              type="range"
              min="0"
              max="5000"
              step="100"
              value={settings.request_delay}
              onChange={(e) => setSettings({ ...settings, request_delay: Number(e.target.value) })}
              className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:cursor-pointer"
            />
          </div>
        </div>
      </div>

      {/* System Info */}
      <div className="glass-card p-5">
        <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2 mb-4">
          <Server className="w-4 h-4 text-slate-400" />
          Информация о системе
        </h2>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Версия сервера</span>
            <span className="text-xs font-medium text-slate-200 font-mono">{sysStatus?.version ?? '—'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Аптайм</span>
            <span className="text-xs font-medium text-slate-200">
              {sysStatus?.uptime_seconds ? formatUptime(sysStatus.uptime_seconds) : '—'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Использование диска</span>
            <div className="flex items-center gap-2">
              <div className="w-20 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    (sysStatus?.disk_usage_percent ?? 0) > 80 ? 'bg-red-500' :
                    (sysStatus?.disk_usage_percent ?? 0) > 60 ? 'bg-amber-500' :
                    'bg-emerald-500'
                  }`}
                  style={{ width: `${sysStatus?.disk_usage_percent ?? 0}%` }}
                />
              </div>
              <span className="text-xs font-medium text-slate-200">{sysStatus?.disk_usage_percent ?? 0}%</span>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Backend</span>
            {sysStatus?.backend_healthy ? (
              <span className="text-xs font-medium text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> Работает
              </span>
            ) : (
              <span className="text-xs font-medium text-red-400 flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" /> Недоступен
              </span>
            )}
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">LLM сервер</span>
            {sysStatus?.llm_connected ? (
              <span className="text-xs font-medium text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> Подключён
              </span>
            ) : (
              <span className="text-xs font-medium text-amber-400 flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" /> Нет соединения
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
          <AlertCircle className="w-4 h-4 text-red-400" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {success && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <p className="text-sm text-emerald-400">Настройки сохранены</p>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium bg-blue-500 text-white hover:bg-blue-600 transition-colors shadow-lg shadow-blue-500/20"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Сохранить
        </button>
        <button
          onClick={handleReset}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium text-slate-400 border border-slate-700 hover:bg-slate-800/50 transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          Сбросить
        </button>
      </div>

      {/* Info note */}
      <div className="flex items-start gap-2 p-3 rounded-lg bg-slate-800/30">
        <Info className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
        <p className="text-xs text-slate-500">
          Изменения вступают в силу для новых задач. Текущие задачи продолжат работать с прежними настройками.
        </p>
      </div>
    </div>
  )
}
