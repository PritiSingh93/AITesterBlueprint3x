import TopNav from './components/TopNav.jsx'
import PipelineFlow from './components/PipelineFlow.jsx'
import DocumentPanel from './components/DocumentPanel.jsx'
import TestCasePanel from './components/TestCasePanel.jsx'

export default function App() {
  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <PipelineFlow />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <DocumentPanel />
          <TestCasePanel />
        </div>
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-center text-xs text-slate-400 sm:px-6 lg:px-8">
        RAG Test Case Generator &middot; Mistral Embed + ChromaDB + Groq
      </footer>
    </div>
  )
}
