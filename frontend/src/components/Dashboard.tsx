import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ListTodo,
  Users,
  Globe,
  Gauge,
  Activity,
  Server,
  HardDrive,
  Brain,
  Clock,
  Coins,
  ArrowUpRight,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import { getDashboardStats, getLLMStatus, getSystemStatus } from '../api'
import type { DashboardStats, LLMStatus, SystemStatus, TaskResponse } from '../types'

// ── SVG Line Chart ────────────────────────────────────────────────────────────

function LineChart({ data }: { data: { date: string; count: number }[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-500 text-sm">
        Нет данных
      </div>
    )
  }

  const maxVal = Math.max(...data.map(d => d.count), 1)
  const width = 600
  const height = 200
  const padding = { top: 20, right: 20, bottom: 40, left: 50 }
  const chartW = width - padding.left - padding.right
  const chartH = height - padding.top - padding.bottom

  const points = data.map((d, i) => ({
    x: padding.left + (i / Math.max(data.length - 1, 1)) * chartW,
    y: padding.top + chartH - (d.count / maxVal) * chartH,
    ...d,
  }))

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${padding.top + chartH} L ${points[0].x} ${padding.top + chartH} Z`

  // Y-axis labels
  const ySteps = 4
  const yLabels = Array.from({ length: ySteps + 1 }, (_, i) => Math.round((maxVal / ySteps) * i))

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="lineGradient" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>
      </defs>

      {/* Grid lines */}
      {yLabels.map((val, i) => {
        const y = padding.top + chartH - (val / maxVal) * chartH
        return (
          <g key={i}>
            <line
              x1={padding.left}
              y1={y}
              x2={padding.left + chartW}
              y2={y}
              stroke="#334155"
              strokeWidth="0.5"
              strokeDasharray="4 4"
            />
            <text x={padding.left - 8} y={y + 4} textAnchor="end" fill="#64748b" fontSize="10">
              {val}
            </text>
          </g>
        )
      })}

      {/* Area fill */}
      <path d={areaPath} fill="url(#chartGradient)" />

      {/* Line */}
      <path d={linePath} fill="none" stroke="url(#lineGradient)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

      {/* Data points */}
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r="4" fill="#0f172a" stroke="#3b82f6" strokeWidth="2" />
          {/* X-axis labels */}
          <text x={p.x} y={height - 8} textAnchor="middle" fill="#64748b" fontSize="10">
            {new Date(p.date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
          </text>
        </g>
      ))}
    </svg>
  )
}

// ── Status Badge helper ────────────────────────────────────────────────────────

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

// ── KPI Card ────────────────────────────────────────────────────────────────

function KPICard({
  icon: Icon,
  label,
  value,
  color = 'blue',
}: {
  icon: React.ElementType
  label: string
  value: string | number
  color?: 'blue' | 'green' | 'amber' | 'purple'
}) {
  const colorMap = {
    blue: 'from-blue-500/20 to-blue-500/5 text-blue-400',
    green: 'from-emerald-500/20 to-emerald-500/5 text-emerald-400',
    amber: 'from-amber-500/20 to-amber-500/5 text-amber-400',
    purple: 'from-violet-500/20 to-violet-500/5 text-violet-400',
  }

  const iconBg = {
    blue: 'bg-blue-500/10 text-blue-400',
    green: 'bg-emerald-500/10 text-emerald-400',
    amber: 'bg-amber-500/10 text-amber-400',
    purple: 'bg-violet-500/10 text-violet-400',
  }

  return (
    <div className="kpi-card">
      <div className={`absolute inset-0 bg-gradient-to-br ${colorMap[color]} opacity-30 rounded-xl`} />
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${iconBg[color]}`}>
            <Icon className="w-5 h-5" />
          </div>
          <ArrowUpRight className="w-4 h-4 text-slate-600" />
        </div>
        <p className="text-2xl font-bold text-white mb-1">{value}</p>
        <p className="text-xs text-slate-400">{label}</p>
      </div>
    </div>
  )
}

// ── Main Dashboard Component ──────────────────────────────────────────────────

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [llmStatus, setLlmStatus] = useState<LLMStatus | null>(null)
  const [sysStatus, setSysStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [s, l, sys] = await Promise.all([
          getDashboardStats(),
          getLLMStatus(),
          getSystemStatus(),
        ])
        if (!cancelled) {
          setStats(s)
          setLlmStatus(l)
          setSysStatus(sys)
        }
      } catch (err) {
        console.error('Dashboard load error:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 30_000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    )
  }

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${seconds}с`
    if (seconds < 3600) return `${Math.round(seconds / 60)}м`
    return `${Math.round(seconds / 3600)}ч`
  }

  return (
    <div className="animate-fade-in space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-slate-400 mt-1">Обзор системы и статистика</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          icon={ListTodo}
          label="Всего задач"
          value={stats?.total_tasks ?? 0}
          color="blue"
        />
        <KPICard
          icon={Users}
          label="Контактов найдено"
          value={stats?.total_contacts ?? 0}
          color="green"
        />
        <KPICard
          icon={Globe}
          label="Сайтов обработано"
          value={stats?.total_sites_processed ?? 0}
          color="purple"
        />
        <KPICard
          icon={Gauge}
          label="Средняя скорость"
          value={stats?.avg_speed ? formatTime(stats.avg_speed) : '—'}
          color="amber"
        />
      </div>

      {/* Chart + Recent Tasks row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart */}
        <div className="lg:col-span-2 glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400" />
            Контакты по дням
          </h2>
          <LineChart data={stats?.contacts_by_day ?? []} />
        </div>

        {/* Recent Tasks */}
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-blue-400" />
            Последние задачи
          </h2>
          <div className="space-y-3">
            {(stats?.recent_tasks ?? []).length === 0 ? (
              <p className="text-xs text-slate-500 text-center py-4">Нет задач</p>
            ) : (
              (stats?.recent_tasks ?? []).map((task: TaskResponse) => (
                <button
                  key={task.task_id}
                  onClick={() => navigate(`/tasks/${task.task_id}`)}
                  className="w-full flex items-center justify-between p-3 rounded-lg bg-slate-800/30 hover:bg-slate-800/60 transition-colors text-left"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-slate-300 truncate">
                      {task.task_id.slice(0, 8)}...
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5">
                      {new Date(task.created_at).toLocaleDateString('ru-RU')}
                    </p>
                  </div>
                  {statusBadge(task.status)}
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Bottom row: LLM Status + System Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* LLM Status */}
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <Brain className="w-4 h-4 text-violet-400" />
            Статус LLM
          </h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Модель</span>
              <span className="text-xs font-medium text-slate-200">{llmStatus?.model_name ?? '—'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Токенов сегодня</span>
              <span className="text-xs font-medium text-slate-200 flex items-center gap-1.5">
                <Coins className="w-3.5 h-3.5 text-amber-400" />
                {llmStatus?.tokens_used_today?.toLocaleString('ru-RU') ?? 0}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Средн. время ответа</span>
              <span className="text-xs font-medium text-slate-200">
                {llmStatus?.avg_response_time ? `${llmStatus.avg_response_time.toFixed(1)}с` : '—'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Статус</span>
              {llmStatus?.is_connected ? (
                <span className="text-xs font-medium text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Подключено
                </span>
              ) : (
                <span className="text-xs font-medium text-red-400 flex items-center gap-1">
                  <XCircle className="w-3.5 h-3.5" /> Отключено
                </span>
              )}
            </div>
          </div>
        </div>

        {/* System Status */}
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            <Server className="w-4 h-4 text-cyan-400" />
            Система
          </h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Backend</span>
              {sysStatus?.backend_healthy ? (
                <span className="text-xs font-medium text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Работает
                </span>
              ) : (
                <span className="text-xs font-medium text-red-400 flex items-center gap-1">
                  <XCircle className="w-3.5 h-3.5" /> Недоступен
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
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Диск</span>
              <div className="flex items-center gap-2">
                <div className="w-24 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      (sysStatus?.disk_usage_percent ?? 0) > 80
                        ? 'bg-red-500'
                        : (sysStatus?.disk_usage_percent ?? 0) > 60
                        ? 'bg-amber-500'
                        : 'bg-emerald-500'
                    }`}
                    style={{ width: `${sysStatus?.disk_usage_percent ?? 0}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-slate-200">
                  <HardDrive className="w-3.5 h-3.5 inline mr-1" />
                  {sysStatus?.disk_usage_percent ?? 0}%
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Версия</span>
              <span className="text-xs font-medium text-slate-200">{sysStatus?.version ?? '—'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
