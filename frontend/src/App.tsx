import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import TaskForm from './components/TaskForm'
import TaskList from './components/TaskList'
import TaskProgress from './components/TaskProgress'
import TaskResults from './components/TaskResults'
import AIAssistant from './components/AIAssistant'
import BlacklistUpload from './components/BlacklistUpload'
import Settings from './components/Settings'

function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center animate-fade-in">
      <p className="text-6xl font-bold text-slate-800 mb-4">404</p>
      <p className="text-slate-500 text-lg mb-6">Страница не найдена</p>
      <a
        href="/"
        className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors"
      >
        На главную
      </a>
    </div>
  )
}

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  useEffect(() => {
    document.title = 'Contact Parser AI'
  }, [])

  // Responsive: auto-collapse on small screens
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 768) {
        setSidebarCollapsed(true)
      }
    }
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-950">
        {/* Sidebar */}
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        />

        {/* Main content */}
        <main
          className={`
            min-h-screen transition-all duration-200
            ${sidebarCollapsed ? 'ml-[68px]' : 'ml-[240px]'}
          `}
        >
          <div className="p-6 lg:p-8 max-w-7xl">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/new" element={<TaskForm />} />
              <Route path="/tasks" element={<TaskList />} />
              <Route path="/tasks/:taskId" element={<TaskProgress />} />
              <Route path="/tasks/:taskId/results" element={<TaskResults />} />
              <Route path="/ai" element={<AIAssistant />} />
              <Route path="/blacklist" element={<BlacklistUpload />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  )
}
