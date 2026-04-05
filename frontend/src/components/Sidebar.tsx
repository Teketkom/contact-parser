// React import removed - no state needed
import { useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  PlusCircle,
  ListTodo,
  Bot,
  ShieldBan,
  Settings,
  ChevronLeft,
  ChevronRight,
  Zap,
  User,
} from 'lucide-react'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

interface NavItem {
  icon: React.ElementType
  label: string
  path: string
}

const navItems: NavItem[] = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: PlusCircle, label: 'Новая задача', path: '/new' },
  { icon: ListTodo, label: 'Задачи', path: '/tasks' },
  { icon: Bot, label: 'AI Ассистент', path: '/ai' },
  { icon: ShieldBan, label: 'Чёрный список', path: '/blacklist' },
  { icon: Settings, label: 'Настройки', path: '/settings' },
]

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const navigate = useNavigate()
  const location = useLocation()

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  return (
    <aside
      className={`
        fixed top-0 left-0 h-screen z-40
        bg-slate-900/95 backdrop-blur-xl
        border-r border-slate-800/80
        flex flex-col
        sidebar-transition
        ${collapsed ? 'w-[68px]' : 'w-[240px]'}
      `}
    >
      {/* Logo area */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-slate-800/80 shrink-0">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center shrink-0">
          <Zap className="w-5 h-5 text-white" />
        </div>
        {!collapsed && (
          <div className="animate-fade-in overflow-hidden">
            <h1 className="text-sm font-bold text-white whitespace-nowrap leading-tight">
              Contact Parser
            </h1>
            <p className="text-[10px] text-slate-500 whitespace-nowrap leading-tight">
              AI-powered extraction
            </p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-2 overflow-y-auto no-scrollbar">
        <div className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon
            const active = isActive(item.path)
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                title={collapsed ? item.label : undefined}
                className={`
                  w-full flex items-center gap-3 rounded-lg transition-all duration-150
                  ${collapsed ? 'justify-center px-2 py-2.5' : 'px-3 py-2.5'}
                  ${active
                    ? 'bg-blue-500/15 text-blue-400 border border-blue-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent'
                  }
                `}
              >
                <Icon className={`w-[18px] h-[18px] shrink-0 ${active ? 'text-blue-400' : ''}`} />
                {!collapsed && (
                  <span className="text-sm font-medium whitespace-nowrap overflow-hidden animate-fade-in">
                    {item.label}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </nav>

      {/* Bottom section: user + collapse toggle */}
      <div className="border-t border-slate-800/80 p-2 space-y-2 shrink-0">
        {/* User avatar */}
        <div
          className={`
            flex items-center gap-3 rounded-lg px-3 py-2.5
            ${collapsed ? 'justify-center px-2' : ''}
          `}
        >
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shrink-0">
            <User className="w-4 h-4 text-white" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden animate-fade-in">
              <p className="text-xs font-medium text-slate-300 truncate">Пользователь</p>
              <p className="text-[10px] text-slate-500 truncate">Администратор</p>
            </div>
          )}
        </div>

        {/* Collapse toggle */}
        <button
          onClick={onToggle}
          className={`
            w-full flex items-center gap-2 rounded-lg px-3 py-2
            text-slate-500 hover:text-slate-300 hover:bg-slate-800/60
            transition-colors
            ${collapsed ? 'justify-center px-2' : ''}
          `}
          title={collapsed ? 'Развернуть' : 'Свернуть'}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span className="text-xs animate-fade-in">Свернуть</span>
            </>
          )}
        </button>
      </div>
    </aside>
  )
}
