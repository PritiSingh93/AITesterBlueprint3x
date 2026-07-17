const API_BASE = import.meta.env.VITE_API_BASE_URL || 'https://rag-testcase-backend.onrender.com'

async function request(path, options = {}, retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Request failed (${res.status})`)
      }
      return res.json()
    } catch (err) {
      if (attempt === retries) {
        throw err
      }
      await new Promise((resolve) => setTimeout(resolve, 300 * (attempt + 1)))
    }
  }
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

  generateBatch: (module, count, startIndex, excludeTitles) =>
    request('/api/query', {
      method: 'POST',
      body: JSON.stringify({
        question: `Generate test cases for the ${module} module`,
        module,
        count,
        start_index: startIndex,
        exclude_titles: excludeTitles,
      }),
    }),
}
