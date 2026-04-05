import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Send,
  Bot,
  User,
  Loader2,
  Copy,
  Check,
  Sparkles,
  Trash2,
  MessageSquare,
} from 'lucide-react'
import { sendAIMessage } from '../api'
import type { AIChatMessage } from '../types'

// System prompt presets
const PRESETS = [
  {
    label: 'Найти компании по отрасли',
    prompt: 'Ты — помощник по поиску компаний. Помоги найти компании определённой отрасли в России. Предложи список сайтов для парсинга.',
    placeholder: 'Например: Найди IT-компании в Москве...',
  },
  {
    label: 'Предложить похожие сайты',
    prompt: 'Ты — эксперт по анализу бизнеса. На основе описания или списка компаний предложи похожие организации и их сайты.',
    placeholder: 'Опишите компанию или отрасль...',
  },
  {
    label: 'Обогатить данные',
    prompt: 'Ты — аналитик данных. Помоги обогатить информацию о контактах: проверь корректность данных, предложи дополнительные источники.',
    placeholder: 'Введите данные для проверки...',
  },
]

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

export default function AIAssistant() {
  const [messages, setMessages] = useState<AIChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [activePreset, setActivePreset] = useState(0)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return

    const userMsg: AIChatMessage = {
      id: generateId(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }

    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const response = await sendAIMessage({
        message: text,
        system_prompt: PRESETS[activePreset].prompt,
      })

      const aiMsg: AIChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, aiMsg])
    } catch (err) {
      const errorMsg: AIChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: `Ошибка: ${err instanceof Error ? err.message : 'Не удалось получить ответ от AI сервера'}`,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleCopy = (id: string, content: string) => {
    navigator.clipboard.writeText(content).then(() => {
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    })
  }

  const clearChat = () => {
    setMessages([])
  }

  return (
    <div className="animate-fade-in flex flex-col h-[calc(100vh-7rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Bot className="w-5 h-5 text-violet-400" />
            AI Ассистент
          </h1>
          <p className="text-sm text-slate-400 mt-1">Чат с AI для поиска и анализа данных</p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearChat}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-slate-500 hover:text-slate-300 border border-slate-800 hover:border-slate-700 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Очистить
          </button>
        )}
      </div>

      {/* System prompt presets */}
      <div className="flex gap-2 overflow-x-auto no-scrollbar pb-3 shrink-0">
        {PRESETS.map((preset, i) => (
          <button
            key={i}
            onClick={() => setActivePreset(i)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
              activePreset === i
                ? 'bg-violet-500/15 text-violet-400 border border-violet-500/30'
                : 'text-slate-400 hover:text-slate-300 border border-transparent hover:bg-slate-800/40'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            {preset.label}
          </button>
        ))}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto no-scrollbar space-y-4 py-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500/20 to-blue-500/20 flex items-center justify-center mb-4">
              <MessageSquare className="w-8 h-8 text-violet-400" />
            </div>
            <h3 className="text-sm font-semibold text-slate-300 mb-2">Начните диалог с AI</h3>
            <p className="text-xs text-slate-500 max-w-sm">
              Задайте вопрос или воспользуйтесь одним из шаблонов выше.
              AI поможет найти компании, предложить похожие сайты или обогатить данные.
            </p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
            >
              <div className={`flex gap-3 max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                {/* Avatar */}
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-br from-blue-500 to-cyan-500'
                    : 'bg-gradient-to-br from-violet-500 to-purple-600'
                }`}>
                  {msg.role === 'user' ? (
                    <User className="w-4 h-4 text-white" />
                  ) : (
                    <Bot className="w-4 h-4 text-white" />
                  )}
                </div>

                {/* Bubble */}
                <div className="space-y-1">
                  <div className={msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai'}>
                    <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  </div>
                  <div className={`flex items-center gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <span className="text-[10px] text-slate-600">
                      {new Date(msg.timestamp).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    {msg.role === 'assistant' && (
                      <button
                        onClick={() => handleCopy(msg.id, msg.content)}
                        className="p-1 rounded text-slate-600 hover:text-slate-400 transition-colors"
                        title="Копировать"
                      >
                        {copiedId === msg.id ? (
                          <Check className="w-3 h-3 text-emerald-400" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="flex justify-start animate-fade-in">
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="chat-bubble-ai">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
                  <span className="text-sm text-slate-400">Думаю...</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="shrink-0 pt-3 border-t border-slate-800/50">
        <div className="glass-card flex items-end gap-3 p-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={PRESETS[activePreset].placeholder}
            rows={1}
            className="flex-1 bg-transparent border-0 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:ring-0 max-h-32"
            style={{ minHeight: '24px' }}
            onInput={(e) => {
              const el = e.currentTarget
              el.style.height = 'auto'
              el.style.height = Math.min(el.scrollHeight, 128) + 'px'
            }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className={`p-2.5 rounded-lg transition-all ${
              input.trim() && !loading
                ? 'bg-blue-500 text-white hover:bg-blue-600 shadow-lg shadow-blue-500/20'
                : 'bg-slate-800 text-slate-600 cursor-not-allowed'
            }`}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[10px] text-slate-600 text-center mt-2">
          Shift + Enter для новой строки · Enter для отправки
        </p>
      </div>
    </div>
  )
}
