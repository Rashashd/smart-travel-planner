import { useState, type FormEvent } from 'react'
import { api } from '../api'

interface Props { onSwitch: () => void }

const perks = [
  { icon: '🤖', title: 'AI Trip Planning', desc: 'Get personalised itineraries in seconds' },
  { icon: '🌍', title: '150+ Destinations', desc: 'Curated knowledge base from Wikivoyage' },
  { icon: '📊', title: 'Smart Classification', desc: 'We match trips to your travel style' },
  { icon: '💬', title: 'Chat History', desc: 'All your plans saved and accessible' },
]

export default function Register({ onSwitch }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.register(email, password)
      onSwitch()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4"
      style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0c4a6e 100%)' }}>

      <div className="absolute top-0 left-0 w-96 h-96 rounded-full opacity-20 blur-3xl"
        style={{ background: 'radial-gradient(circle, #38bdf8, transparent)' }} />
      <div className="absolute bottom-0 right-0 w-96 h-96 rounded-full opacity-20 blur-3xl"
        style={{ background: 'radial-gradient(circle, #a78bfa, transparent)' }} />

      <div className="w-full max-w-5xl rounded-3xl shadow-2xl overflow-hidden flex min-h-[600px] relative z-10">

        {/* ── Left panel ── */}
        <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-10 relative overflow-hidden"
          style={{ background: 'linear-gradient(145deg, #0f172a 0%, #1e1b4b 60%, #312e81 100%)' }}>

          <div className="absolute -top-16 -right-16 w-64 h-64 rounded-full opacity-10 border-4 border-white" />
          <div className="absolute -bottom-24 -left-12 w-72 h-72 rounded-full opacity-10 border-4 border-white" />

          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-3xl">🗺️</span>
              <span className="text-white font-bold text-xl tracking-wide">Smart Travel Planner</span>
            </div>
            <p className="text-indigo-300 text-sm leading-relaxed max-w-xs">
              Join thousands of travellers planning smarter trips with AI.
            </p>
          </div>

          {/* Perks */}
          <div className="space-y-3 my-6">
            <p className="text-white/50 text-xs uppercase tracking-widest mb-4">What you get</p>
            {perks.map((p, i) => (
              <div key={i} className="flex items-start gap-3 bg-white/10 backdrop-blur-sm rounded-2xl p-3 border border-white/10">
                <span className="text-2xl flex-shrink-0">{p.icon}</span>
                <div>
                  <p className="text-white text-sm font-semibold">{p.title}</p>
                  <p className="text-white/50 text-xs">{p.desc}</p>
                </div>
              </div>
            ))}
          </div>

          <p className="text-white/30 text-xs text-center">Free forever · No credit card required</p>
        </div>

        {/* ── Right panel ── */}
        <div className="w-full lg:w-1/2 bg-white flex flex-col justify-center px-10 py-12 relative">
          <div className="absolute top-6 right-8 text-2xl">🌐</div>

          <div className="mb-8">
            <h2 className="text-4xl font-bold mb-1"
              style={{ background: 'linear-gradient(90deg, #6366f1, #a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Start Exploring
            </h2>
            <p className="text-gray-400 text-sm">Create your free account in seconds</p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">Email</label>
              <div className="flex items-center border-2 border-gray-100 rounded-2xl px-4 py-3 focus-within:border-indigo-400 transition-colors bg-gray-50">
                <span className="text-gray-400 mr-3 text-lg">✉️</span>
                <input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  className="flex-1 text-sm outline-none bg-transparent text-gray-700 placeholder-gray-300"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">Password</label>
              <div className="flex items-center border-2 border-gray-100 rounded-2xl px-4 py-3 focus-within:border-indigo-400 transition-colors bg-gray-50">
                <span className="text-gray-400 mr-3 text-lg">🔒</span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Min. 8 characters"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  minLength={8}
                  className="flex-1 text-sm outline-none bg-transparent text-gray-700 placeholder-gray-300"
                />
                <button type="button" onClick={() => setShowPassword(v => !v)}
                  className="text-xs text-indigo-400 hover:text-indigo-600 font-medium ml-2">
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-1.5 ml-1">Use at least 8 characters</p>
            </div>

            {error && (
              <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-4 py-2">
                <span className="text-sm">⚠️</span>
                <p className="text-red-500 text-sm">{error}</p>
              </div>
            )}

            <button type="submit" disabled={loading}
              className="w-full text-white rounded-2xl py-3 text-sm font-bold tracking-wider uppercase disabled:opacity-50 transition-all hover:shadow-lg hover:scale-[1.01] active:scale-[0.99]"
              style={{ background: 'linear-gradient(90deg, #6366f1, #a855f7)' }}>
              {loading ? 'Creating account…' : '🌍 Create Account'}
            </button>
          </form>

          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-gray-100" />
            <span className="text-gray-300 text-xs">HAVE AN ACCOUNT?</span>
            <div className="flex-1 h-px bg-gray-100" />
          </div>

          <button onClick={onSwitch}
            className="w-full border-2 border-gray-100 hover:border-indigo-300 rounded-2xl py-3 text-sm font-semibold text-gray-600 hover:text-indigo-500 transition-all">
            Sign In Instead
          </button>
        </div>
      </div>
    </div>
  )
}
