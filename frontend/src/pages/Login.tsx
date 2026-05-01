import { useState, type FormEvent } from 'react'
import { useAuth } from '../AuthContext'

interface Props { onSwitch: () => void }

const destinations = [
  { name: 'Bali, Indonesia', emoji: '🌴', tag: 'Beach & Culture', color: 'from-orange-400 to-pink-500' },
  { name: 'Kyoto, Japan', emoji: '⛩️', tag: 'History & Nature', color: 'from-purple-400 to-indigo-500' },
  { name: 'Santorini, Greece', emoji: '🏛️', tag: 'Luxury & Views', color: 'from-sky-400 to-blue-600' },
]

export default function Login({ onSwitch }: Props) {
  const { login } = useAuth()
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
      await login(email, password)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4"
      style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0c4a6e 100%)' }}>

      {/* Background blobs */}
      <div className="absolute top-0 left-0 w-96 h-96 rounded-full opacity-20 blur-3xl"
        style={{ background: 'radial-gradient(circle, #38bdf8, transparent)' }} />
      <div className="absolute bottom-0 right-0 w-96 h-96 rounded-full opacity-20 blur-3xl"
        style={{ background: 'radial-gradient(circle, #f472b6, transparent)' }} />

      <div className="w-full max-w-5xl rounded-3xl shadow-2xl overflow-hidden flex min-h-[600px] relative z-10">

        {/* ── Left panel ── */}
        <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-10 relative overflow-hidden"
          style={{ background: 'linear-gradient(145deg, #0f172a 0%, #0c4a6e 60%, #164e63 100%)' }}>

          {/* Decorative circles */}
          <div className="absolute -top-16 -right-16 w-64 h-64 rounded-full opacity-10 border-4 border-white" />
          <div className="absolute -bottom-24 -left-12 w-72 h-72 rounded-full opacity-10 border-4 border-white" />

          {/* Brand */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-3xl">🗺️</span>
              <span className="text-white font-bold text-xl tracking-wide">Smart Travel Planner</span>
            </div>
            <p className="text-sky-300 text-sm leading-relaxed max-w-xs">
              Your AI-powered travel companion. Plan, explore, and discover your next adventure.
            </p>
          </div>

          {/* Destination cards */}
          <div className="space-y-3 my-6">
            <p className="text-white/50 text-xs uppercase tracking-widest mb-4">Popular Destinations</p>
            {destinations.map((d, i) => (
              <div key={i}
                className="flex items-center gap-3 bg-white/10 backdrop-blur-sm rounded-2xl p-3 border border-white/10">
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${d.color} flex items-center justify-center text-lg flex-shrink-0`}>
                  {d.emoji}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm font-medium truncate">{d.name}</p>
                  <p className="text-white/50 text-xs">{d.tag}</p>
                </div>
                <span className="text-white/40 text-xs">→</span>
              </div>
            ))}
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-3">
            {[['150+', 'Destinations'], ['6', 'Trip Types'], ['AI', 'Powered']].map(([val, label]) => (
              <div key={label} className="bg-white/10 rounded-2xl p-3 text-center border border-white/10">
                <p className="text-white font-bold text-lg">{val}</p>
                <p className="text-white/50 text-xs">{label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Right panel ── */}
        <div className="w-full lg:w-1/2 bg-white flex flex-col justify-center px-10 py-12 relative">
          <div className="absolute top-6 right-8 text-2xl">✈️</div>

          {/* Heading */}
          <div className="mb-8">
            <h2 className="text-4xl font-bold mb-1"
              style={{ background: 'linear-gradient(90deg, #0ea5e9, #6366f1)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Welcome Back
            </h2>
            <p className="text-gray-400 text-sm">Sign in to plan your next journey</p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            {/* Email */}
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">Email</label>
              <div className="flex items-center border-2 border-gray-100 rounded-2xl px-4 py-3 focus-within:border-sky-400 transition-colors bg-gray-50">
                <span className="text-gray-400 mr-3 text-sm font-medium">@</span>
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

            {/* Password */}
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">Password</label>
              <div className="flex items-center border-2 border-gray-100 rounded-2xl px-4 py-3 focus-within:border-sky-400 transition-colors bg-gray-50">
                <span className="text-gray-400 mr-3 text-sm">••</span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  className="flex-1 text-sm outline-none bg-transparent text-gray-700 placeholder-gray-300"
                />
                <button type="button" onClick={() => setShowPassword(v => !v)}
                  className="text-xs text-sky-400 hover:text-sky-600 font-medium ml-2">
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-4 py-2">
                <span className="text-red-400 text-sm">⚠️</span>
                <p className="text-red-500 text-sm">{error}</p>
              </div>
            )}

            <button type="submit" disabled={loading}
              className="w-full text-white rounded-2xl py-3 text-sm font-bold tracking-wider uppercase disabled:opacity-50 transition-all hover:shadow-lg hover:scale-[1.01] active:scale-[0.99]"
              style={{ background: 'linear-gradient(90deg, #0ea5e9, #6366f1)' }}>
              {loading ? 'Signing in…' : '🚀 Sign In'}
            </button>
          </form>

          {/* Divider */}
          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-gray-100" />
            <span className="text-gray-500 text-xs font-semibold">NEW HERE?</span>
            <div className="flex-1 h-px bg-gray-100" />
          </div>

          <button onClick={onSwitch}
            className="w-full border-2 border-gray-400 hover:border-sky-400 rounded-2xl py-3 text-sm font-semibold text-gray-600 hover:text-sky-500 transition-all">
            Create an Account
          </button>
        </div>
      </div>
    </div>
  )
}
