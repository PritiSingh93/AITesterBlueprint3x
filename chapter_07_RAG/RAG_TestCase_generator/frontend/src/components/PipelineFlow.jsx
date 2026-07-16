import { useEffect, useState } from 'react'
import { ArrowRight, Boxes, ClipboardList, Database, FileText, Scissors, Search } from 'lucide-react'
import { api } from '../api.js'

const STEPS = [
  { icon: FileText, label: 'PRD / Text', hint: 'load requirements' },
  { icon: Scissors, label: 'Chunk', hint: 'split text' },
  { icon: Boxes, label: 'Embed', hint: 'Mistral vectors' },
  { icon: Database, label: 'Store', hint: 'ChromaDB' },
  { icon: Search, label: 'Retrieve', hint: 'top-K' },
  { icon: ClipboardList, label: 'Test Cases', hint: 'Groq LLM' },
]

export default function PipelineFlow() {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    api.status().then(setStatus).catch(() => {})
  }, [])

  return (
    <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">
            PRD &rarr; Chunk &rarr; Mistral Embed &rarr; ChromaDB &rarr; Retrieve top-K &rarr; Groq Test Cases
          </h2>
          <p className="text-xs text-slate-500">The complete RAG pipeline, end to end</p>
        </div>
        {status && (
          <div className="flex flex-wrap gap-1.5">
            <StatusPill label="ChromaDB" />
            <StatusPill label={status.embedding_model} />
            <StatusPill label={status.groq_model} />
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap sm:overflow-x-auto sm:pb-1">
        {STEPS.map(({ icon: Icon, label, hint }, i) => (
          <div key={label} className="flex items-center gap-2">
            <div className="flex min-w-[7.5rem] flex-col items-center gap-1.5 rounded-xl bg-slate-50 px-3 py-3 text-center">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white">
                {i + 1}
              </div>
              <Icon className="h-4 w-4 text-brand-600" />
              <div>
                <p className="text-xs font-semibold text-slate-700">{label}</p>
                <p className="text-[10px] text-slate-400">{hint}</p>
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <ArrowRight className="h-4 w-4 shrink-0 text-slate-300" />
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

function StatusPill({ label }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
      {label}
    </span>
  )
}
