import { useState } from 'react'
import TopNav from './components/TopNav.jsx'
import RagFlowTab from './components/RagFlowTab.jsx'
import EmbeddingExplorerTab from './components/EmbeddingExplorerTab.jsx'

export default function App() {
  const [tab, setTab] = useState('rag')

  return (
    <div className="min-h-screen">
      <TopNav tab={tab} setTab={setTab} />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        {tab === 'rag' ? <RagFlowTab /> : <EmbeddingExplorerTab />}
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-center text-xs text-slate-400 sm:px-6 lg:px-8">
        RAG Explorer &middot; Nomic Embed + ChromaDB + Groq
      </footer>
    </div>
  )
}
