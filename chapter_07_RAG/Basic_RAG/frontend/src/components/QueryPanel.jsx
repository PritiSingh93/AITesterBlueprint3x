import { useState } from 'react'
import { Loader2, Search, Sparkles } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api.js'

const SUGGESTED_QUESTIONS = [
  'What is this document and what problem does it solve?',
  'Who are the target users?',
  'What are the core features?',
  'What are the non-functional requirements?',
]

export default function QueryPanel() {
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const runQuery = async (text) => {
    if (!text.trim()) return
    setQuestion(text)
    setLoading(true)
    setError('')
    setResult(null)
    try {
      setResult(await api.query(text))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleAsk = (event) => {
    event.preventDefault()
    runQuery(question)
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-4 flex items-center gap-2 text-base font-semibold">
        <Search className="h-5 w-5 text-brand-600" />
        Ask a Question
      </h2>

      <form onSubmit={handleAsk} className="mb-3 flex gap-2">
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="e.g. What problem does this document aim to solve?"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
        />
        <button
          type="submit"
          disabled={loading}
          className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:opacity-60"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          Ask
        </button>
      </form>

      <div className="mb-4 flex flex-wrap gap-1.5">
        {SUGGESTED_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            disabled={loading}
            onClick={() => runQuery(q)}
            className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-60"
          >
            {q}
          </button>
        ))}
      </div>

      {error && (
        <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
      )}

      {result && (
        <div className="space-y-4">
          <div className="rounded-xl bg-brand-50 p-4">
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-brand-700">
              Answer &middot; {result.model}
            </h3>
            <div className="prose prose-sm prose-slate max-w-none prose-p:my-1.5 prose-ul:my-1.5 prose-li:my-0.5">
              <ReactMarkdown>{result.answer}</ReactMarkdown>
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Retrieved Chunks (top {result.retrieved_chunks.length})
            </h3>
            <div className="space-y-2">
              {result.retrieved_chunks.map((c, i) => (
                <div key={c.id} className="rounded-lg border border-slate-200 p-3 text-xs">
                  <div className="mb-1.5 flex items-center justify-between gap-2 text-slate-500">
                    <span className="truncate font-medium text-slate-700">
                      #{i + 1} &middot; {c.source} (chunk {c.chunk_index})
                    </span>
                    <span className="whitespace-nowrap rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-600">
                      similarity {c.similarity}
                    </span>
                  </div>
                  <p className="max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed text-slate-600">
                    {c.text}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {!result && !loading && !error && (
        <p className="rounded-lg border border-dashed border-slate-200 p-4 text-center text-sm text-slate-400">
          Ingest documents on the left, then ask a question (or pick a suggestion above) to see
          retrieval + generation in action.
        </p>
      )}
    </section>
  )
}
