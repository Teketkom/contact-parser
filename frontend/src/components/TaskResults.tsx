import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Loader2,
  Download,
  FileText,
  Users,
  Search,
  Building2,
  Briefcase,
  ChevronUp,
  ChevronDown,
  ArrowLeft,
  Filter,
  X,
} from 'lucide-react'
import { getTask, downloadResults, downloadLogs } from '../api'
import type { TaskResponse, ContactRecord } from '../types'
import api from '../api'

// Category definitions
const CATEGORIES = [
  { key: 'all', label: 'Все контакты', icon: Users },
  { key: 'director', label: 'Директора', icon: Briefcase },
  { key: 'lawyer', label: 'Юрист', icon: Briefcase },
  { key: 'cfo', label: 'Финансовый директор', icon: Briefcase },
  { key: 'hr', label: 'HR', icon: Briefcase },
  { key: 'other', label: 'Прочие', icon: Briefcase },
]

function categorizeContact(c: ContactRecord): string {
  const pos = (c.position_normalized ?? c.position_raw ?? '').toLowerCase()
  if (pos.includes('директор') && !pos.includes('финанс') && !pos.includes('hr') && !pos.includes('кадр')) return 'director'
  if (pos.includes('юрист') || pos.includes('юридич') || pos.includes('правов')) return 'lawyer'
  if (pos.includes('финанс') || pos.includes('бухгалт') || pos.includes('cfo') || pos.includes('главный бухгалтер')) return 'cfo'
  if (pos.includes('hr') || pos.includes('кадр') || pos.includes('персонал') || pos.includes('рекрут')) return 'hr'
  return 'other'
}

type SortField = 'full_name' | 'company_name' | 'position_normalized' | 'personal_email' | 'phone' | 'inn'
type SortDir = 'asc' | 'desc'

export default function TaskResults() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [task, setTask] = useState<TaskResponse | null>(null)
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [, setError] = useState<string | null>(null)
  const [activeCategory, setActiveCategory] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [sortField, setSortField] = useState<SortField>('full_name')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  useEffect(() => {
    if (!taskId) return
    let cancelled = false

    async function loadData() {
      try {
        const [taskData, contactsResp] = await Promise.all([
          getTask(taskId!),
          api.get<ContactRecord[]>(`/tasks/${taskId}/contacts`).catch(() => ({ data: [] as ContactRecord[] })),
        ])
        if (!cancelled) {
          setTask(taskData)
          setContacts(contactsResp.data)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Ошибка загрузки результатов')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadData()
    return () => { cancelled = true }
  }, [taskId])

  // Filtered and sorted contacts
  const filteredContacts = useMemo(() => {
    let result = contacts

    // Category filter
    if (activeCategory !== 'all') {
      result = result.filter(c => categorizeContact(c) === activeCategory)
    }

    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      result = result.filter(c =>
        (c.full_name ?? '').toLowerCase().includes(q) ||
        (c.company_name ?? '').toLowerCase().includes(q) ||
        (c.position_normalized ?? c.position_raw ?? '').toLowerCase().includes(q) ||
        (c.personal_email ?? '').toLowerCase().includes(q) ||
        (c.phone ?? '').toLowerCase().includes(q) ||
        (c.inn ?? '').toLowerCase().includes(q)
      )
    }

    // Sort
    result = [...result].sort((a, b) => {
      const valA = (a[sortField] ?? '').toLowerCase()
      const valB = (b[sortField] ?? '').toLowerCase()
      return sortDir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA)
    })

    return result
  }, [contacts, activeCategory, searchQuery, sortField, sortDir])

  // Category counts
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: contacts.length }
    contacts.forEach(c => {
      const cat = categorizeContact(c)
      counts[cat] = (counts[cat] ?? 0) + 1
    })
    return counts
  }, [contacts])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('asc')
    }
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="opacity-0 group-hover:opacity-30"><ChevronUp className="w-3 h-3" /></span>
    return sortDir === 'asc' ? <ChevronUp className="w-3 h-3 text-blue-400" /> : <ChevronDown className="w-3 h-3 text-blue-400" />
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    )
  }

  return (
    <div className="animate-fade-in space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => navigate(`/tasks/${taskId}`)}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 mb-2 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            К задаче
          </button>
          <h1 className="text-xl font-bold text-white">Результаты</h1>
          <p className="text-sm text-slate-400 mt-1">
            {task?.task_id?.slice(0, 8)} — {contacts.length} контактов
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => taskId && downloadResults(taskId)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
          >
            <Download className="w-4 h-4" />
            Скачать Excel
          </button>
          <button
            onClick={() => taskId && downloadLogs(taskId)}
            className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-400 border border-slate-700 hover:bg-slate-800/50 transition-colors"
          >
            <FileText className="w-4 h-4" />
            Логи
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="glass-card p-4 text-center">
          <p className="text-2xl font-bold text-white">{contacts.length}</p>
          <p className="text-xs text-slate-400 mt-1">Всего контактов</p>
        </div>
        <div className="glass-card p-4 text-center">
          <p className="text-2xl font-bold text-blue-400">{categoryCounts.director ?? 0}</p>
          <p className="text-xs text-slate-400 mt-1">Директора</p>
        </div>
        <div className="glass-card p-4 text-center">
          <p className="text-2xl font-bold text-violet-400">{categoryCounts.lawyer ?? 0}</p>
          <p className="text-xs text-slate-400 mt-1">Юристы</p>
        </div>
        <div className="glass-card p-4 text-center">
          <p className="text-2xl font-bold text-amber-400">{categoryCounts.cfo ?? 0}</p>
          <p className="text-xs text-slate-400 mt-1">Фин. директора</p>
        </div>
      </div>

      {/* Category tabs */}
      <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.key}
            onClick={() => setActiveCategory(cat.key)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
              activeCategory === cat.key
                ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30'
                : 'text-slate-400 hover:text-slate-300 border border-transparent hover:bg-slate-800/40'
            }`}
          >
            <cat.icon className="w-3.5 h-3.5" />
            {cat.label}
            <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] ${
              activeCategory === cat.key ? 'bg-blue-500/20 text-blue-300' : 'bg-slate-800/50 text-slate-500'
            }`}>
              {categoryCounts[cat.key] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Поиск по ФИО, компании, email, телефону..."
          className="glass-input w-full pl-10 pr-8"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Results table */}
      <div className="glass-card overflow-hidden">
        {filteredContacts.length === 0 ? (
          <div className="text-center py-16">
            <Filter className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <p className="text-sm text-slate-500">
              {contacts.length === 0 ? 'Контакты не найдены' : 'Нет результатов по фильтру'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="dark-table">
              <thead>
                <tr>
                  <th className="group cursor-pointer" onClick={() => handleSort('full_name')}>
                    <span className="flex items-center gap-1">ФИО <SortIcon field="full_name" /></span>
                  </th>
                  <th className="group cursor-pointer" onClick={() => handleSort('company_name')}>
                    <span className="flex items-center gap-1">Компания <SortIcon field="company_name" /></span>
                  </th>
                  <th className="group cursor-pointer" onClick={() => handleSort('position_normalized')}>
                    <span className="flex items-center gap-1">Должность <SortIcon field="position_normalized" /></span>
                  </th>
                  <th className="group cursor-pointer" onClick={() => handleSort('personal_email')}>
                    <span className="flex items-center gap-1">Email <SortIcon field="personal_email" /></span>
                  </th>
                  <th className="group cursor-pointer" onClick={() => handleSort('phone')}>
                    <span className="flex items-center gap-1">Телефон <SortIcon field="phone" /></span>
                  </th>
                  <th className="group cursor-pointer" onClick={() => handleSort('inn')}>
                    <span className="flex items-center gap-1">ИНН <SortIcon field="inn" /></span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredContacts.map((contact, i) => (
                  <tr key={i}>
                    <td>
                      <span className="font-medium text-slate-200">{contact.full_name || '—'}</span>
                    </td>
                    <td>
                      <div className="flex items-center gap-1.5">
                        <Building2 className="w-3 h-3 text-slate-500 shrink-0" />
                        <span className="text-xs truncate max-w-[180px]">{contact.company_name || '—'}</span>
                      </div>
                    </td>
                    <td>
                      <span className="text-xs">{contact.position_normalized ?? contact.position_raw ?? '—'}</span>
                    </td>
                    <td>
                      {contact.personal_email ? (
                        <a
                          href={`mailto:${contact.personal_email}`}
                          className="text-xs text-blue-400 hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {contact.personal_email}
                        </a>
                      ) : (
                        <span className="text-xs text-slate-600">—</span>
                      )}
                    </td>
                    <td>
                      <span className="text-xs font-mono">{contact.phone || '—'}</span>
                    </td>
                    <td>
                      <span className="text-xs font-mono">{contact.inn || '—'}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {filteredContacts.length > 0 && (
          <div className="px-4 py-3 border-t border-slate-800/50 text-xs text-slate-500">
            Показано {filteredContacts.length} из {contacts.length} контактов
          </div>
        )}
      </div>
    </div>
  )
}
