import { NavLink } from 'react-router-dom'
import { List, Plus, Shield } from 'lucide-react'

export default function Header() {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
        {/* Logo */}
        <NavLink to="/" className="flex items-center gap-2.5 flex-shrink-0">
          <div className="w-8 h-8 flex-shrink-0">
            <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Логотип парсера">
              <rect width="32" height="32" rx="8" fill="#2563eb"/>
              <path d="M7 10h10M7 16h14M7 22h8" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
              <circle cx="24" cy="22" r="4.5" fill="#2563eb" stroke="white" strokeWidth="2"/>
              <path d="M27 25l3 3" stroke="white" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>
          <div className="hidden sm:block">
            <span className="font-semibold text-slate-900 text-sm leading-tight block">
              Парсер контактной
            </span>
            <span className="text-slate-500 text-xs leading-tight block">
              информации
            </span>
          </div>
        </NavLink>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`
            }
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Новая задача</span>
          </NavLink>

          <NavLink
            to="/tasks"
            className={({ isActive }) =>
              `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`
            }
          >
            <List className="w-4 h-4" />
            <span className="hidden sm:inline">Задачи</span>
          </NavLink>

          <NavLink
            to="/blacklist"
            className={({ isActive }) =>
              `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`
            }
          >
            <Shield className="w-4 h-4" />
            <span className="hidden sm:inline">Чёрный список</span>
          </NavLink>
        </nav>
      </div>
    </header>
  )
}
