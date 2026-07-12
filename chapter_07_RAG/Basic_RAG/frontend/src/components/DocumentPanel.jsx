import { useEffect, useState } from 'react'
import { CheckCircle2, FileText, Layers, RefreshCw, UploadCloud } from 'lucide-react'
import { api } from '../api.js'

export default function DocumentPanel() {
  const [status, setStatus] = useState(null)
  const [chunks, setChunks] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const refreshStatus = async () => {
    try {
      setStatus(await api.status())
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    refreshStatus()
  }, [])

  const handleIngest = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.ingest()
      setChunks(res.chunks)
      await refreshStatus()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError('')
    try {
      await api.upload(file)
      await refreshStatus()
    } catch (e) {
      setError(e.message)
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <FileText className="h-5 w-5 text-brand-600" />
          Document Ingestion
        </h2>
        {status && (
          <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
            <CheckCircle2 className="h-3.5 w-3.5" />
            {status.chunk_count} chunks stored
          </span>
        )}
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={handleIngest}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-3.5 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-brand-700 disabled:opacity-60"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          {loading ? 'Ingesting…' : 'Run Ingestion Pipeline'}
        </button>

        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50">
          <UploadCloud className="h-4 w-4" />
          {uploading ? 'Uploading…' : 'Upload PDF / Text'}
          <input
            type="file"
            accept=".pdf,.txt,.md"
            className="hidden"
            onChange={handleUpload}
            disabled={uploading}
          />
        </label>
      </div>

      {error && (
        <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
      )}

      <div>
        <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-slate-700">
          <Layers className="h-4 w-4" />
          Chunk Preview {chunks.length > 0 && `(${chunks.length})`}
        </h3>
        <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
          {chunks.length === 0 && (
            <p className="rounded-lg border border-dashed border-slate-200 p-4 text-center text-sm text-slate-400">
              Run the ingestion pipeline to see chunks here.
            </p>
          )}
          {chunks.map((c) => (
            <div key={c.id} className="rounded-lg border border-slate-200 p-3 text-xs">
              <div className="mb-1 flex items-center justify-between gap-2 text-slate-500">
                <span className="truncate font-medium text-slate-700">{c.source}</span>
                <span className="flex items-center gap-1.5 whitespace-nowrap">
                  chunk #{c.chunk_index} &middot; ~{c.est_tokens} tokens
                  {c.extraction_method === 'ocr' && (
                    <span
                      title="No text layer found in this PDF — extracted via OCR"
                      className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700"
                    >
                      OCR
                    </span>
                  )}
                </span>
              </div>
              <p className="whitespace-pre-wrap leading-relaxed text-slate-600">{c.preview}…</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
