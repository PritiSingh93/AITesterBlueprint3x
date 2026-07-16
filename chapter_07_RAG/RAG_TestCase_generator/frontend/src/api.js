const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed (${res.status})`)
  }
  return res.json()
}

export const api = {
  status: () => request('/api/status'),

  ingest: () => request('/api/ingest', { method: 'POST' }),

  upload: async (file) => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: form })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || 'Upload failed')
    }
    return res.json()
  },

  query: (question, topK) =>
    request('/api/query', {
      method: 'POST',
      body: JSON.stringify({ question, top_k: topK }),
    }),

  generateBatch: (module, count) =>
    request('/api/query', {
      method: 'POST',
      body: JSON.stringify({
        question: `Generate test cases for the ${module} module`,
        module,
        count,
      }),
    }),
}
