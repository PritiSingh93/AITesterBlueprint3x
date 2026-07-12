import { useEffect, useState } from 'react'
import { GitCompareArrows, ScatterChart as ScatterIcon, Type } from 'lucide-react'
import { api } from '../api.js'
import SimilarityGauge from './SimilarityGauge.jsx'
import VectorBars from './VectorBars.jsx'
import WordScatterChart from './WordScatterChart.jsx'

export default function EmbeddingExplorerTab() {
  const [sampleText, setSampleText] = useState('artificial intelligence')
  const [vectorResult, setVectorResult] = useState(null)
  const [vectorLoading, setVectorLoading] = useState(false)

  const [wordA, setWordA] = useState('King')
  const [wordB, setWordB] = useState('Queen')
  const [compareResult, setCompareResult] = useState(null)
  const [compareLoading, setCompareLoading] = useState(false)

  const [points, setPoints] = useState([])
  const [projectLoading, setProjectLoading] = useState(false)

  const [error, setError] = useState('')

  useEffect(() => {
    ;(async () => {
      setProjectLoading(true)
      try {
        const res = await api.embedProject()
        setPoints(res.points)
      } catch (e) {
        setError(e.message)
      } finally {
        setProjectLoading(false)
      }
    })()
  }, [])

  const handleVectorize = async () => {
    if (!sampleText.trim()) return
    setVectorLoading(true)
    setError('')
    try {
      setVectorResult(await api.embedVector(sampleText))
    } catch (e) {
      setError(e.message)
    } finally {
      setVectorLoading(false)
    }
  }

  const handleCompare = async () => {
    if (!wordA.trim() || !wordB.trim()) return
    setCompareLoading(true)
    setError('')
    try {
      setCompareResult(await api.embedCompare(wordA, wordB))
    } catch (e) {
      setError(e.message)
    } finally {
      setCompareLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <Type className="h-5 w-5 text-brand-600" />
            Text &rarr; Vector
          </h2>
          <p className="mb-3 text-xs text-slate-500">
            Type any word or sentence to see its real embedding vector from Nomic Embed.
          </p>
          <div className="mb-3 flex gap-2">
            <input
              value={sampleText}
              onChange={(event) => setSampleText(event.target.value)}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              placeholder="Type any word or sentence"
            />
            <button
              type="button"
              onClick={handleVectorize}
              disabled={vectorLoading}
              className="shrink-0 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:opacity-60"
            >
              {vectorLoading ? 'Embedding…' : 'Embed'}
            </button>
          </div>
          {vectorResult && (
            <>
              <p className="mb-2 text-xs text-slate-500">
                {vectorResult.dimensions}-dimensional vector &middot; first 24 values shown
              </p>
              <VectorBars values={vectorResult.vector_preview} />
            </>
          )}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <GitCompareArrows className="h-5 w-5 text-brand-600" />
            Similarity Comparison
          </h2>
          <p className="mb-3 text-xs text-slate-500">
            Compare how close two concepts are in embedding space (e.g. "King" vs "Queen").
          </p>
          <div className="mb-3 grid grid-cols-2 gap-2">
            <input
              value={wordA}
              onChange={(event) => setWordA(event.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              placeholder="Word A"
            />
            <input
              value={wordB}
              onChange={(event) => setWordB(event.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              placeholder="Word B"
            />
          </div>
          <button
            type="button"
            onClick={handleCompare}
            disabled={compareLoading}
            className="mb-4 w-full rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:opacity-60"
          >
            {compareLoading ? 'Comparing…' : 'Compare'}
          </button>
          {compareResult && (
            <SimilarityGauge
              value={compareResult.cosine_similarity}
              labelA={compareResult.text_a}
              labelB={compareResult.text_b}
            />
          )}
        </section>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
          <ScatterIcon className="h-5 w-5 text-brand-600" />
          Word Embedding Map (2D projection)
        </h2>
        <p className="mb-4 text-xs text-slate-500">
          Real Nomic embeddings for common word pairs, projected to 2D via PCA. Related concepts
          (king/queen, man/woman) cluster together.
        </p>
        <WordScatterChart points={points} loading={projectLoading} />
      </section>
    </div>
  )
}
