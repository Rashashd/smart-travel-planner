const BASE = ''

function token() {
  return localStorage.getItem('token')
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Request failed')
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  register: (email: string, password: string) =>
    request<{ id: string; email: string }>('POST', '/auth/register', { email, password }),

  login: async (email: string, password: string) => {
    const form = new URLSearchParams({ username: email, password })
    const res = await fetch('/auth/login', { method: 'POST', body: form })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? 'Login failed')
    }
    const data: { access_token: string } = await res.json()
    localStorage.setItem('token', data.access_token)
    return data
  },

  logout: () => localStorage.removeItem('token'),

  me: () => request<{ id: string; email: string }>('GET', '/auth/me'),

  chat: (question: string, session_id?: string) =>
    request<{ answer: string; session_id: string; tool_calls: unknown[] }>('POST', '/chat', {
      question,
      session_id: session_id ?? null,
    }),

  sessions: () =>
    request<{ id: string; title: string; created_at: string }[]>('GET', '/sessions'),

  messages: (sessionId: string) =>
    request<{ role: string; content: string; created_at: string; tool_calls?: { tool_name: string; input_json: string; output_json: string | null }[] }[]>(
      'GET',
      `/sessions/${sessionId}/messages`
    ),

  deleteSession: (sessionId: string) =>
    request<void>('DELETE', `/sessions/${sessionId}`),

  deleteAccount: () =>
    request<void>('DELETE', '/auth/me'),
}
