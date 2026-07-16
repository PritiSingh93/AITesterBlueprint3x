import { ClipboardCheck } from 'lucide-react'

export default function TopNav() {
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-sm">
            <ClipboardCheck className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold leading-tight">RAG Test Case Generator</h1>
            <p className="text-xs leading-tight text-slate-500">
              Ingest requirements &middot; Retrieve context &middot; Generate test cases
            </p>
          </div>
        </div>
      </div>
    </header>
  )
}
