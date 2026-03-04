import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, useNavigate, useParams } from 'react-router-dom'
import Header from './components/Header'
import TaskForm from './components/TaskForm'
import TaskProgress from './components/TaskProgress'
import TaskResults from './components/TaskResults'
import TaskList from './components/TaskList'
import BlacklistUpload from './components/BlacklistUpload'

// ── Page wrappers ──────────────────────────────────────────────────────────────────

function HomePage() {
  const navigate = useNavigate()

  const handleTaskCreated = (taskId: string) => {
    navigate(`/tasks/${taskId}`)
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-slate-900 mb-1">
          Новая задача парсинга
        </h1>
        <p className="text-slate-500 text-sm">
          Загрузите файл со списком сайтов и настройте параметры извлечения контактов
        </p>
      </div>
      <TaskForm onTaskCreated={handleTaskCreated} />
    </div>
  )
}

function TaskPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [showResults, setShowResults] = useState(false)

  if (!taskId) {
    navigate('/')
    return null
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 animate-fade-in">
      {!showResults ? (
        <TaskProgress
          taskId={taskId}
          onCompleted={() => setShowResults(true)}
        />
      ) : (
        <TaskResults taskId={taskId} />
      )}
    </div>
  )
}

function TasksPage() {
  return (
    <div className="max-w-5xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-slate-900 mb-1">
          История задач
        </h1>
        <p className="text-slate-500 text-sm">
          Все задачи парсинга с их статусами и результатами
        </p>
      </div>
      <TaskList />
    </div>
  )
}

function BlacklistPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-slate-900 mb-1">
          Чёрный список
        </h1>
        <p className="text-slate-500 text-sm">
          Домены, исключённые из обработки
        </p>
      </div>
      <BlacklistUpload />
    </div>
  )
}

// ── App root ────────────────────────────────────────────────────────────────────────────

export default function App() {
  // Update document title based on app state
  useEffect(() => {
    document.title = 'Парсер контактной информации'
  }, [])

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50 flex flex-col">
        <Header />
        <main className="flex-1 pb-12">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/tasks/:taskId" element={<TaskPage />} />
            <Route path="/blacklist" element={<BlacklistPage />} />
            <Route path="*" element={
              <div className="max-w-3xl mx-auto px-4 py-16 text-center">
                <p className="text-6xl font-bold text-slate-200 mb-4">404</p>
                <p className="text-slate-500 text-lg mb-6">Страница не найдена</p>
                <a
                  href="/"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors"
                >
                  На главную
                </a>
              </div>
            } />
          </Routes>
        </main>
        <footer className="border-t border-slate-200 py-4 text-center text-xs text-slate-400">
          Парсер контактной информации
        </footer>
      </div>
    </BrowserRouter>
  )
}
