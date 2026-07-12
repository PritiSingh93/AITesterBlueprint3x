import { LayoutGrid, Orbit, Sparkles } from 'lucide-react'

const TABS = [
  { id: 'rag', label: 'RAG Flow', icon: LayoutGrid },
  { id: 'embeddings', label: 'Embedding Explorer', icon: Orbit },
]

export default function TopNav({ tab, setTab }) {
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-sm">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold leading-tight">RAG Explorer</h1>
            <p className="text-xs leading-tight text-slate-500">
              Ingestion &middot; Chunking &middot; Embedding &middot; Retrieval &middot; Answering
            </p>
          </div>
        </div>

        <nav className="flex gap-1 rounded-xl bg-slate-100 p-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                tab === id
                  ? 'bg-white text-brand-700 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </nav>
      </div>
    </header>
  )
}
