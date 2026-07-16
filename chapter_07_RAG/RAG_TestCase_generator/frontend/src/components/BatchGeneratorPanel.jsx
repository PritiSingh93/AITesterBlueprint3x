import { useRef, useState } from 'react'
import { Download, ListChecks, Play, Square } from 'lucide-react'
import { api } from '../api.js'

const DEFAULT_MODULES = [
  'Login',
  'Registration',
  'Dashboard',
  'Product Search',
  'Product Details',
  'Add to Cart',
  'Checkout',
  'Payment',
  'Order History',
  'Account Settings',
].join('\n')

const CSV_HEADER = ['TC ID', 'Module', 'Type', 'Title', 'Preconditions', 'Steps', 'Expected Result']

function parseMarkdownTable(markdown, moduleFallback) {
  const lines = markdown
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.startsWith('|'))

  const rows = []
  for (const line of lines) {
    // Skip separator rows like |---|:---:|---|
    if (/^\|[\s:|-]+\|$/.test(line)) continue
    const cells = line
      .split('|')
      .slice(1, -1)
      .map((c) => c.trim())
    if (cells.length < 6) continue
    const [tcId, module, type, title, preconditions, steps, expected = ''] = cells
    if (tcId.toLowerCase().replace(/\s+/g, '') === 'tcid') continue // header row
    rows.push({
      tcId: tcId || '',
      module: module || moduleFallback,
      type: type || '',
      title: title || '',
      preconditions: preconditions || '',
      steps: steps || '',
      expected: expected || '',
    })
  }
  return rows
}

function csvEscape(value) {
  return `"${String(value ?? '').replace(/"/g, '""')}"`
}

function downloadCsv(rows) {
  const lines = [CSV_HEADER.map(csvEscape).join(',')]
  for (const r of rows) {
    lines.push(
      [r.tcId, r.module, r.type, r.title, r.preconditions, r.steps, r.expected]
        .map(csvEscape)
        .join(','),
    )
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `test_cases_${Date.now()}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export default function BatchGeneratorPanel() {
  const [modulesText, setModulesText] = useState(DEFAULT_MODULES)
  const [perModuleTarget, setPerModuleTarget] = useState(100)
  const [batchSize, setBatchSize] = useState(20)
  const [running, setRunning] = useState(false)
  const [rows, setRows] = useState([])
  const [errors, setErrors] = useState([])
  const [progress, setProgress] = useState(null)
  const stopRef = useRef(false)

  const modules = modulesText
    .split('\n')
    .map((m) => m.trim())
    .filter(Boolean)
  const totalTarget = modules.length * perModuleTarget

  const runBatch = async () => {
    if (modules.length === 0 || running) return
    stopRef.current = false
    setRunning(true)
    setRows([])
    setErrors([])
    const allRows = []

    for (let mi = 0; mi < modules.length; mi++) {
      if (stopRef.current) break
      const moduleName = modules[mi]
      let generated = 0
      let attempts = 0
      const maxAttempts = Math.ceil(perModuleTarget / batchSize) + 3

      while (generated < perModuleTarget && !stopRef.current) {
        attempts += 1
        if (attempts > maxAttempts) {
          setErrors((prev) => [...prev, `${moduleName}: stopped after repeated empty/failed responses`])
          break
        }

        const remaining = perModuleTarget - generated
        const thisBatch = Math.min(batchSize, remaining)
        setProgress({
          moduleIndex: mi,
          moduleName,
          moduleGenerated: generated,
          moduleTarget: perModuleTarget,
          totalGenerated: allRows.length,
          totalTarget,
        })

        try {
          const res = await api.generateBatch(moduleName, thisBatch)
          const parsed = parseMarkdownTable(res.answer, moduleName)
          if (parsed.length === 0) {
            setErrors((prev) => [...prev, `${moduleName}: got an unparseable response, retrying`])
            continue
          }
          allRows.push(...parsed)
          generated += parsed.length
          setRows([...allRows])
        } catch (e) {
          setErrors((prev) => [...prev, `${moduleName}: ${e.message}`])
          break
        }

        await new Promise((resolve) => setTimeout(resolve, 400))
      }
    }

    setProgress((p) => (p ? { ...p, totalGenerated: allRows.length } : p))
    setRunning(false)
  }

  const stopBatch = () => {
    stopRef.current = true
  }

  return (
    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <ListChecks className="h-5 w-5 text-brand-600" />
          Batch Test Case Generator
        </h2>
        <span className="text-xs text-slate-500">
          {modules.length} modules &middot; target {totalTarget} test cases
        </span>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="sm:col-span-2">
          <label className="mb-1 block text-xs font-medium text-slate-600">
            Modules (one per line)
          </label>
          <textarea
            value={modulesText}
            onChange={(e) => setModulesText(e.target.value)}
            disabled={running}
            rows={6}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:bg-slate-50"
          />
        </div>
        <div className="flex flex-col gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">
              Test cases per module
            </label>
            <input
              type="number"
              min={1}
              value={perModuleTarget}
              onChange={(e) => setPerModuleTarget(Math.max(1, Number(e.target.value) || 1))}
              disabled={running}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:bg-slate-50"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">
              Batch size per request
            </label>
            <input
              type="number"
              min={1}
              max={30}
              value={batchSize}
              onChange={(e) => setBatchSize(Math.min(30, Math.max(1, Number(e.target.value) || 1)))}
              disabled={running}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:bg-slate-50"
            />
          </div>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {!running ? (
          <button
            type="button"
            onClick={runBatch}
            disabled={modules.length === 0}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-3.5 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-brand-700 disabled:opacity-60"
          >
            <Play className="h-4 w-4" />
            Generate All
          </button>
        ) : (
          <button
            type="button"
            onClick={stopBatch}
            className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-3.5 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-red-700"
          >
            <Square className="h-4 w-4" />
            Stop
          </button>
        )}
        <button
          type="button"
          onClick={() => downloadCsv(rows)}
          disabled={rows.length === 0}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-60"
        >
          <Download className="h-4 w-4" />
          Export CSV ({rows.length})
        </button>
        {progress && (
          <span className="text-xs text-slate-500">
            Module {progress.moduleIndex + 1}/{modules.length} &middot; {progress.moduleName}
            {' '}({progress.moduleGenerated}/{progress.moduleTarget}) &middot; total{' '}
            {progress.totalGenerated}/{progress.totalTarget}
          </span>
        )}
      </div>

      {errors.length > 0 && (
        <div className="mb-3 space-y-1">
          {errors.map((e, i) => (
            <p key={i} className="rounded-lg bg-amber-50 px-3 py-1.5 text-xs text-amber-700">
              {e}
            </p>
          ))}
        </div>
      )}

      <div className="max-h-96 overflow-auto rounded-lg border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-xs">
          <thead className="sticky top-0 bg-slate-50">
            <tr>
              {CSV_HEADER.map((h) => (
                <th key={h} className="px-2 py-1.5 text-left font-semibold text-slate-600">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-slate-400">
                  No test cases generated yet. Set your modules and click Generate All.
                </td>
              </tr>
            )}
            {rows.map((r, i) => (
              <tr key={i} className="align-top">
                <td className="whitespace-nowrap px-2 py-1.5 text-slate-500">{r.tcId}</td>
                <td className="whitespace-nowrap px-2 py-1.5 text-slate-500">{r.module}</td>
                <td className="whitespace-nowrap px-2 py-1.5 text-slate-500">{r.type}</td>
                <td className="px-2 py-1.5 text-slate-700">{r.title}</td>
                <td className="px-2 py-1.5 text-slate-500">{r.preconditions}</td>
                <td className="px-2 py-1.5 text-slate-500">{r.steps}</td>
                <td className="px-2 py-1.5 text-slate-500">{r.expected}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
