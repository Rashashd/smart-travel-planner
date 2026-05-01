import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { useAuth } from '../AuthContext'
import { api } from '../api'

interface ToolCall { tool_name: string; input_json: string; output_json: string | null }
interface Message { role: 'user' | 'assistant'; content: string; tool_calls?: ToolCall[] }
interface Session { id: string; title: string; created_at: string }

const TOOL_META: Record<string, { icon: string; label: string }> = {
  get_live_conditions:          { icon: '🌤️', label: 'Live Conditions' },
  search_destination_knowledge: { icon: '📚', label: 'Destination Knowledge' },
  classify_destination:         { icon: '🏷️', label: 'Travel Style' },
  web_search:                   { icon: '🔍', label: 'Web Search' },
}

function summarizeInput(toolName: string, inputJson: string): string {
  try {
    const d = JSON.parse(inputJson)
    switch (toolName) {
      case 'get_live_conditions':          return `${d.city}, ${d.country}`
      case 'search_destination_knowledge': return d.query ?? ''
      case 'classify_destination':         return `${d.avg_temp_c}°C · beach ${d.beach_score}/10 · culture ${d.cultural_sites_score}/10`
      case 'web_search':                   return d.query ?? ''
      default: return ''
    }
  } catch { return '' }
}

function summarizeOutput(toolName: string, outputJson: string | null): string {
  if (!outputJson) return '—'
  try {
    const d = JSON.parse(outputJson)
    if (d?.error) return `Error: ${d.error}`
    switch (toolName) {
      case 'classify_destination': {
        const style = d.predicted_style ?? '?'
        const prob  = d.probabilities?.[style]
        return prob != null ? `${style} · ${Math.round(prob * 100)}% confidence` : style
      }
      case 'get_live_conditions': {
        const parts: string[] = []
        if (d.weather?.temp_c   != null) parts.push(`${d.weather.temp_c}°C`)
        if (d.weather?.precipitation_mm != null) parts.push(`${d.weather.precipitation_mm}mm rain`)
        if (d.flights?.cheapest_round_trip_usd) parts.push(`flights ~$${d.flights.cheapest_round_trip_usd}`)
        return parts.join(' · ') || 'Retrieved'
      }
      case 'search_destination_knowledge': {
        if (!Array.isArray(d)) return 'Retrieved'
        const dest = d[0]?.destination ?? ''
        const sim  = d[0]?.similarity  != null ? ` · ${Math.round(d[0].similarity * 100)}% match` : ''
        return `${d.length} chunk${d.length !== 1 ? 's' : ''}${dest ? ` on ${dest}` : ''}${sim}`
      }
      case 'web_search':
        return Array.isArray(d) ? `${d.length} result${d.length !== 1 ? 's' : ''}` : 'Retrieved'
      default:
        return 'Done'
    }
  } catch { return 'Done' }
}

function ToolCallPanel({ calls }: { calls: ToolCall[] }) {
  const [open, setOpen] = useState(false)
  if (!calls?.length) return null

  return (
    <div className="mt-2 text-xs">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 text-sky-600 hover:text-sky-800 font-medium transition-colors"
      >
        <span>{open ? '▾' : '▸'}</span>
        <span>{calls.length} tool{calls.length > 1 ? 's' : ''} used</span>
        <span className="flex gap-1 ml-1">
          {calls.map((tc, i) => (
            <span key={i} title={(TOOL_META[tc.tool_name] ?? {}).label ?? tc.tool_name}>
              {(TOOL_META[tc.tool_name] ?? {}).icon ?? '🔧'}
            </span>
          ))}
        </span>
      </button>

      {open && (
        <div className="mt-2 space-y-1.5">
          {calls.map((tc, i) => {
            const meta = TOOL_META[tc.tool_name] ?? { icon: '🔧', label: tc.tool_name }
            const inputSummary  = summarizeInput(tc.tool_name, tc.input_json)
            const outputSummary = summarizeOutput(tc.tool_name, tc.output_json)
            return (
              <div key={i} className="flex items-start gap-2 rounded-xl border border-sky-100 bg-white px-3 py-2">
                <span className="text-base leading-none mt-0.5">{meta.icon}</span>
                <div className="min-w-0">
                  <span className="font-semibold text-sky-800">{meta.label}</span>
                  {inputSummary && (
                    <span className="text-gray-400 ml-1.5">· {inputSummary}</span>
                  )}
                  <p className="text-gray-600 mt-0.5 truncate">{outputSummary}</p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function Chat() {
  const { user, logout } = useAuth()
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeSession, setActiveSession] = useState<string | undefined>()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [confirmDeleteAccount, setConfirmDeleteAccount] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.sessions().then(setSessions).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadSession = async (id: string) => {
    setActiveSession(id)
    const msgs = await api.messages(id)
    setMessages(msgs.map(m => ({ role: m.role as 'user' | 'assistant', content: m.content, tool_calls: m.tool_calls })))
  }

  const newChat = () => {
    setActiveSession(undefined)
    setMessages([])
  }

  const deleteSession = async (id: string) => {
    await api.deleteSession(id)
    setSessions(prev => prev.filter(s => s.id !== id))
    if (activeSession === id) {
      setActiveSession(undefined)
      setMessages([])
    }
  }

  const deleteAccount = async () => {
    await api.deleteAccount()
    logout()
  }

  const send = async (e: { preventDefault(): void }) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    const question = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: question }])
    setLoading(true)
    try {
      const res = await api.chat(question, activeSession)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.answer,
        tool_calls: res.tool_calls as ToolCall[],
      }])
      if (!activeSession) {
        setActiveSession(res.session_id)
        const updated = await api.sessions()
        setSessions(updated)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Something went wrong'
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${msg}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">

      {/* ── Sidebar ── */}
      <aside className="w-64 flex-shrink-0 flex flex-col border-r border-white/10"
        style={{ background: '#0f172a' }}>

        {/* Brand */}
        <div className="p-5 border-b border-white/10">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl">🗺️</span>
            <span className="text-white font-bold text-sm tracking-wide">Smart Travel Planner</span>
          </div>
          <p className="text-white/40 text-xs truncate ml-7">{user?.email}</p>
        </div>

        {/* New chat */}
        <div className="p-3">
          <button onClick={newChat}
            className="w-full text-white rounded-2xl py-2.5 text-sm font-semibold flex items-center justify-center gap-2 hover:opacity-90 transition-all hover:scale-[1.02] active:scale-[0.98]"
            style={{ background: 'linear-gradient(90deg, #10b981, #0ea5e9)' }}>
            + New Chat
          </button>
        </div>

        {/* Sessions */}
        <nav className="flex-1 overflow-y-auto px-3 pb-3 space-y-1">
          {sessions.length === 0 && (
            <p className="text-white/30 text-xs text-center mt-4 px-2">No trips planned yet</p>
          )}
          {sessions.map(s => (
            <div key={s.id}
              className={`group flex items-center rounded-xl transition-all ${
                activeSession === s.id
                  ? 'bg-white/15 border border-white/20'
                  : 'hover:bg-white/10 border border-transparent'
              }`}>
              <button onClick={() => loadSession(s.id)}
                className="flex-1 text-left px-3 py-2.5 text-sm truncate flex items-center gap-2">
                <span className="text-base flex-shrink-0">📍</span>
                <span className={activeSession === s.id ? 'text-white font-medium' : 'text-white/70'}>
                  {s.title}
                </span>
              </button>
              <button onClick={() => deleteSession(s.id)}
                className="opacity-0 group-hover:opacity-100 px-2 py-2 text-white/30 hover:text-red-400 transition-all text-xs flex-shrink-0">
                ✕
              </button>
            </div>
          ))}
        </nav>

        {/* Bottom actions */}
        <div className="p-3 border-t border-white/10 space-y-1">
          <button onClick={logout}
            className="w-full text-white/50 hover:text-white text-xs py-2 rounded-xl hover:bg-white/10 transition-all flex items-center justify-center gap-2">
            Sign out
          </button>
          {!confirmDeleteAccount ? (
            <button onClick={() => setConfirmDeleteAccount(true)}
              className="w-full text-red-400/60 hover:text-red-400 text-xs py-1.5 rounded-xl hover:bg-red-400/10 transition-all">
              Delete account
            </button>
          ) : (
            <div className="space-y-1.5 pt-1">
              <p className="text-white/40 text-xs text-center">Are you sure?</p>
              <div className="flex gap-2">
                <button onClick={deleteAccount}
                  className="flex-1 text-xs bg-red-500 hover:bg-red-600 text-white rounded-xl py-1.5 transition-all">
                  Yes, delete
                </button>
                <button onClick={() => setConfirmDeleteAccount(false)}
                  className="flex-1 text-xs border border-white/20 rounded-xl py-1.5 text-white/60 hover:bg-white/10 transition-all">
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* ── Main area ── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-300 flex items-center gap-3" style={{ background: '#dbeafe' }}>
          <span className="text-2xl">🌍</span>
          <div>
            <h1 className="text-gray-800 font-semibold text-sm">
              {activeSession
                ? (sessions.find(s => s.id === activeSession)?.title ?? 'Trip Planning')
                : 'Where to next?'}
            </h1>
            <p className="text-gray-400 text-xs">AI-powered travel planner</p>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center gap-6 text-center">
              <div className="text-6xl">✈️</div>
              <div>
                <p className="text-gray-700 font-semibold text-lg mb-1">Plan your perfect trip</p>
                <p className="text-gray-400 text-sm max-w-sm">
                  Ask me anything — destinations, itineraries, budgets, weather, flights, and more.
                </p>
              </div>
              {/* Suggestion chips */}
              <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                {[
                  '🏖️ Beach trip for 2 weeks in July',
                  '🏔️ Adventure travel on a budget',
                  '🏛️ Cultural tour of Europe',
                  '🌴 Luxury escape in Asia',
                ].map(s => (
                  <button key={s} onClick={() => setInput(s.slice(3))}
                    className="text-sm px-4 py-2 rounded-full border border-gray-300 text-gray-500 hover:text-sky-600 hover:border-sky-400 hover:bg-sky-50 transition-all">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {m.role === 'assistant' && (
                <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm flex-shrink-0 mr-2 mt-1"
                  style={{ background: 'linear-gradient(135deg, #0ea5e9, #6366f1)' }}>
                  🗺️
                </div>
              )}
              <div className="max-w-2xl">
                <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'text-white rounded-br-sm'
                    : 'text-gray-800 rounded-bl-sm'
                }`}
                  style={m.role === 'user'
                    ? { background: '#0284c7' }
                    : { background: '#e0f2fe', border: '1px solid #bae6fd' }}>
                  {m.role === 'user' ? m.content : (
                    <ReactMarkdown
                      components={{
                        h1: ({children}) => <h1 className="text-base font-bold text-sky-800 mb-2 mt-1">{children}</h1>,
                        h2: ({children}) => <h2 className="text-sm font-bold text-sky-700 mb-1.5 mt-2">{children}</h2>,
                        h3: ({children}) => <h3 className="text-sm font-semibold text-indigo-700 mb-1 mt-2 italic">{children}</h3>,
                        strong: ({children}) => <strong className="font-bold text-sky-900">{children}</strong>,
                        em: ({children}) => <em className="italic text-indigo-600">{children}</em>,
                        ul: ({children}) => <ul className="list-none space-y-1 my-2">{children}</ul>,
                        ol: ({children}) => <ol className="list-decimal list-inside space-y-1 my-2 text-gray-700">{children}</ol>,
                        li: ({children}) => <li className="flex items-start gap-1.5"><span className="text-sky-500 mt-0.5 flex-shrink-0">✦</span><span>{children}</span></li>,
                        p: ({children}) => <p className="mb-2 last:mb-0">{children}</p>,
                        a: ({href, children}) => <a href={href} className="text-sky-600 underline hover:text-sky-800">{children}</a>,
                        blockquote: ({children}) => <blockquote className="border-l-4 border-sky-400 pl-3 italic text-gray-600 my-2">{children}</blockquote>,
                        code: ({children}) => <code className="bg-sky-100 text-sky-800 px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>,
                        hr: () => <hr className="border-sky-200 my-3" />,
                      }}
                    >
                      {m.content}
                    </ReactMarkdown>
                  )}
                </div>
                {m.role === 'assistant' && m.tool_calls?.length ? (
                  <ToolCallPanel calls={m.tool_calls} />
                ) : null}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start items-end gap-2">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm flex-shrink-0"
                style={{ background: 'linear-gradient(135deg, #0ea5e9, #6366f1)' }}>
                🗺️
              </div>
              <div className="px-4 py-3 rounded-2xl rounded-bl-sm border border-gray-200 bg-white text-sm text-gray-400">
                <span className="inline-flex gap-1">
                  <span className="animate-bounce" style={{ animationDelay: '0ms' }}>•</span>
                  <span className="animate-bounce" style={{ animationDelay: '150ms' }}>•</span>
                  <span className="animate-bounce" style={{ animationDelay: '300ms' }}>•</span>
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-6 py-4 border-t border-gray-300" style={{ background: '#dbeafe' }}>
          <form onSubmit={send} className="flex gap-3 items-center">
            <div className="flex-1 flex items-center border-2 border-gray-200 rounded-2xl px-4 py-3 focus-within:border-sky-400 transition-colors bg-white">
              <span className="text-gray-400 mr-3 text-lg">💬</span>
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Where do you want to go?"
                disabled={loading}
                className="flex-1 text-sm outline-none bg-transparent text-gray-700 placeholder-gray-300 disabled:opacity-50"
              />
            </div>
            <button type="submit" disabled={loading || !input.trim()}
              className="text-white rounded-2xl px-5 py-3 text-sm font-bold transition-all hover:brightness-110 hover:scale-[1.03] active:scale-[0.97] flex-shrink-0 disabled:cursor-not-allowed"
              style={{ background: input.trim() && !loading ? 'linear-gradient(90deg, #0369a1, #3730a3)' : '#94a3b8' }}>
              Send ✈️
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
