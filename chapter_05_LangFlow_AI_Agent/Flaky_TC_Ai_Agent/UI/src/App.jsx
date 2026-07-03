import { useCallback, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'

const FLOW_ID = import.meta.env.VITE_LANGFLOW_FLOW_ID
const API_KEY = import.meta.env.VITE_LANGFLOW_API_KEY
const LANGFLOW_BASE_URL = import.meta.env.VITE_LANGFLOW_BASE_URL || 'http://localhost:7861'
const LANGFLOW_URL = `${LANGFLOW_BASE_URL}/flow/${FLOW_ID}`
const RUN_URL = `/langflow-api/api/v1/run/${FLOW_ID}?stream=false`

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(reader.error)
    reader.readAsText(file)
  })
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function buildInputValue(name1, json1, name2, json2) {
  return [
    'Compare the two Playwright builds and identify flaky tests, consistent failures, and a rerun recommendation.',
    '',
    `--- ${name1} ---`,
    json1,
    '',
    `--- ${name2} ---`,
    json2,
  ].join('\n')
}

function extractAnswer(payload) {
  const output = payload?.outputs?.[0]?.outputs?.[0]
  const message = output?.results?.message
  const text = message?.text ?? output?.artifacts?.message
  const source = message?.properties?.source
  const usage = message?.properties?.usage
  return {
    text: text ?? 'No response text was returned by the flow.',
    model: source?.source ?? source?.display_name ?? null,
    usage: usage ?? null,
    sessionId: payload?.session_id ?? null,
  }
}

// -- Playwright JSON report comparison (computed locally, independent of the AI response) --

function specOutcome(spec) {
  const tests = spec.tests || []
  if (tests.some((t) => t.status === 'flaky')) return 'flaky'
  if (spec.ok === false) return 'failed'
  if (spec.ok === true) return 'passed'
  const statuses = tests.flatMap((t) => (t.results || []).map((r) => r.status))
  if (statuses.includes('failed') || statuses.includes('timedOut')) return 'failed'
  if (statuses.length && statuses.every((s) => s === 'skipped')) return 'skipped'
  return statuses.length ? 'passed' : 'skipped'
}

function extractTests(report) {
  const tests = new Map()
  const walk = (suite, path) => {
    const nextPath = suite.title ? [...path, suite.title] : path
    for (const spec of suite.specs || []) {
      tests.set([...nextPath, spec.title].join(' › '), specOutcome(spec))
    }
    for (const child of suite.suites || []) walk(child, nextPath)
  }
  for (const suite of report.suites || []) walk(suite, [])
  return tests
}

function compareReports(reportA, reportB) {
  const mapA = extractTests(reportA)
  const mapB = extractTests(reportB)
  const keys = new Set([...mapA.keys(), ...mapB.keys()])
  const buckets = { passed: [], failed: [], flaky: [], skipped: [] }

  for (const key of keys) {
    const a = mapA.get(key)
    const b = mapB.get(key)
    let outcome
    if (a === 'flaky' || b === 'flaky') outcome = 'flaky'
    else if (a && b && a !== b && a !== 'skipped' && b !== 'skipped') outcome = 'flaky'
    else if (a === 'failed' || b === 'failed') outcome = 'failed'
    else if (a === 'passed' || b === 'passed') outcome = 'passed'
    else outcome = 'skipped'
    buckets[outcome].push(key)
  }

  return {
    total: keys.size,
    passed: buckets.passed.length,
    failed: buckets.failed.length,
    flaky: buckets.flaky.length,
    skipped: buckets.skipped.length,
    failedTests: buckets.failed,
    flakyTests: buckets.flaky,
  }
}

function healthFromStats(stats) {
  if (!stats) return null
  if (stats.flaky > 0) return { level: 'warning', label: 'Flaky tests detected' }
  if (stats.failed > 0) return { level: 'critical', label: 'Failures detected' }
  return { level: 'good', label: 'All tests stable' }
}

function UploadSlot({ label, file, onFile, onClear }) {
  const inputRef = useRef(null)
  const [isDragOver, setIsDragOver] = useState(false)

  const handleFiles = useCallback(
    (fileList) => {
      const picked = fileList?.[0]
      if (!picked) return
      onFile(picked)
    },
    [onFile],
  )

  return (
    <div
      className={`upload-slot ${file ? 'has-file' : ''} ${isDragOver ? 'drag-over' : ''}`}
      onDragOver={(e) => {
        e.preventDefault()
        setIsDragOver(true)
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setIsDragOver(false)
        handleFiles(e.dataTransfer.files)
      }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/json,.json"
        hidden
        onChange={(e) => handleFiles(e.target.files)}
      />
      <span className="upload-label">{label}</span>
      {file ? (
        <div className="file-chip">
          <div className="file-chip-info">
            <span className="file-icon">📄</span>
            <div>
              <div className="file-name">{file.name}</div>
              <div className="file-size">{formatBytes(file.size)}</div>
            </div>
          </div>
          <button
            className="clear-btn"
            onClick={(e) => {
              e.stopPropagation()
              onClear()
            }}
            aria-label={`Remove ${label}`}
          >
            ✕
          </button>
        </div>
      ) : (
        <div className="upload-placeholder">
          <span className="upload-icon">⬆</span>
          <p>Drop JSON here or click to browse</p>
        </div>
      )}
    </div>
  )
}

function StatTile({ status, icon, value, label }) {
  return (
    <div className="stat-tile">
      <span className={`stat-icon stat-icon--${status}`}>{icon}</span>
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  )
}

function TestList({ title, status, tests }) {
  if (!tests.length) {
    return (
      <div className="test-list test-list--empty">
        <span className={`dot dot--${status}`} />
        No {title.toLowerCase()} detected.
      </div>
    )
  }
  return (
    <div className="test-list">
      <div className="test-list-header">
        <span className={`dot dot--${status}`} />
        {title} <span className="test-count">({tests.length})</span>
      </div>
      <ul>
        {tests.map((name) => (
          <li key={name}>{name}</li>
        ))}
      </ul>
    </div>
  )
}

export default function App() {
  const [file1, setFile1] = useState(null)
  const [file2, setFile2] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [stats, setStats] = useState(null)

  const canCompare = file1 && file2 && !loading
  const health = healthFromStats(stats)

  const handleCompare = async () => {
    setError(null)
    setResult(null)
    setStats(null)
    setLoading(true)
    try {
      const [text1, text2] = await Promise.all([readFileAsText(file1), readFileAsText(file2)])

      let json1
      let json2
      try {
        json1 = JSON.parse(text1)
      } catch {
        throw new Error(`"${file1.name}" is not valid JSON.`)
      }
      try {
        json2 = JSON.parse(text2)
      } catch {
        throw new Error(`"${file2.name}" is not valid JSON.`)
      }

      setStats(compareReports(json1, json2))

      const inputValue = buildInputValue(
        file1.name,
        JSON.stringify(json1, null, 2),
        file2.name,
        JSON.stringify(json2, null, 2),
      )

      const response = await fetch(RUN_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': API_KEY,
        },
        body: JSON.stringify({
          output_type: 'chat',
          input_type: 'text',
          input_value: inputValue,
          session_id: `session-${Date.now()}`,
        }),
      })

      if (!response.ok) {
        const errBody = await response.text()
        throw new Error(`Request failed (${response.status}): ${errBody || response.statusText}`)
      }

      const payload = await response.json()
      setResult(extractAnswer(payload))
    } catch (err) {
      setError(err.message || 'Something went wrong while comparing the builds.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <header className="top-bar">
        <div className="brand">
          <span className="brand-mark">◆</span>
          Flaky Test Analyzer
        </div>
        <a className="langflow-link" href={LANGFLOW_URL} target="_blank" rel="noopener noreferrer">
          Open in Langflow <span aria-hidden="true">↗</span>
        </a>
      </header>

      <section className="intro">
        <h1>Compare two Playwright builds</h1>
        <p>Upload two result files and the AI agent will spot flaky tests and real failures.</p>
      </section>

      <section className="upload-grid">
        <UploadSlot label="Result 1" file={file1} onFile={setFile1} onClear={() => setFile1(null)} />
        <UploadSlot label="Result 2" file={file2} onFile={setFile2} onClear={() => setFile2(null)} />
      </section>

      <div className="action-row">
        <button className="compare-btn" disabled={!canCompare} onClick={handleCompare}>
          {loading ? 'Comparing…' : 'Compare Builds'}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {stats && (
        <section className="dashboard">
          <div className={`health-banner health-banner--${health.level}`}>
            <span className={`dot dot--${health.level}`} />
            {health.label}
          </div>

          <div className="stat-grid">
            <StatTile status="neutral" icon="Σ" value={stats.total} label="Total tests" />
            <StatTile status="good" icon="✓" value={stats.passed} label="Passed" />
            <StatTile status="critical" icon="✕" value={stats.failed} label="Failed" />
            <StatTile status="warning" icon="⟲" value={stats.flaky} label="Flaky" />
          </div>

          <div className="test-list-grid">
            <TestList title="Flaky tests" status="warning" tests={stats.flakyTests} />
            <TestList title="Consistent failures" status="critical" tests={stats.failedTests} />
          </div>
        </section>
      )}

      {loading && (
        <div className="status-card">
          <span className="spinner" />
          Asking the AI agent for a detailed analysis…
        </div>
      )}

      {result && !loading && (
        <section className="result-card">
          <div className="result-meta">
            <span className="result-title">AI analysis</span>
            {result.model && <span className="badge">{result.model}</span>}
            {result.usage && <span className="badge subtle">{result.usage.total_tokens} tokens</span>}
            {result.sessionId && <span className="badge subtle">{result.sessionId}</span>}
          </div>
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.text}</ReactMarkdown>
          </div>
        </section>
      )}

      {!stats && !loading && !error && (
        <div className="empty-state">Select both result files to run the comparison.</div>
      )}
    </div>
  )
}
