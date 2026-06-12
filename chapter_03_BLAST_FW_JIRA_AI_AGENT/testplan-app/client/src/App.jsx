import React, { useState, useEffect, useMemo } from 'react'
import { generateTestPlan, saveTestPlan, saveStrategy } from './api'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null, info: null }
  }
  componentDidCatch(error, info) {
    console.error('Uncaught render error:', error, info)
    this.setState({ error, info })
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{padding:20}}>
          <h2>Something went wrong rendering the app</h2>
          <pre style={{whiteSpace:'pre-wrap',background:'#fff2e6',padding:12,borderRadius:6}}>{this.state.error && this.state.error.toString()}</pre>
          <details style={{whiteSpace:'pre-wrap'}}>{this.state.info && this.state.info.componentStack}</details>
          <button onClick={() => this.setState({ error: null, info: null })}>Clear</button>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  const [viewMode, setViewMode] = useState('plan') // 'plan' or 'strategy' or 'both'
  const [jiraBaseUrl, setJiraBaseUrl] = useState('')
  const [jiraEmail, setJiraEmail] = useState('')
  const [jiraToken, setJiraToken] = useState('')
  const [groqUrl, setGroqUrl] = useState('')
  const [groqKey, setGroqKey] = useState('')
  const [jiraId, setJiraId] = useState('KAN-4')
  const [result, setResult] = useState('')
  const [strategy, setStrategy] = useState('')
  const [loading, setLoading] = useState(false)
  const [useGroq, setUseGroq] = useState(false)
  const [saveStatus, setSaveStatus] = useState('')
  const [lastResp, setLastResp] = useState(null)

  useEffect(() => {
    const saved = localStorage.getItem('tp_settings')
    if (saved) {
      const s = JSON.parse(saved)
      setJiraBaseUrl(s.jiraBaseUrl || '')
      setJiraEmail(s.jiraEmail || '')
      setJiraToken(s.jiraToken || '')
      setGroqUrl(s.groqUrl || '')
      setGroqKey(s.groqKey || '')
    }
  }, [])

  function saveSettings() {
    localStorage.setItem('tp_settings', JSON.stringify({ jiraBaseUrl, jiraEmail, jiraToken, groqUrl, groqKey }))
    alert('Settings saved locally')
  }

  async function handleGenerate(e) {
    if (e && e.preventDefault) e.preventDefault()
    setLoading(true)
    setResult('')
    try {
      const res = await generateTestPlan({ jiraBaseUrl, jiraEmail, jiraToken, groqApiUrl: groqUrl, groqApiKey: groqKey, jiraId, useGroq })
      console.debug('[client] /api/generate response:', res)
      setLastResp(res)
      const md = res.markdown || JSON.stringify(res)
      setResult(md)
      // prefer server-provided strategy, but derive one from the markdown or fields if missing
      let strat = ''
      if (res && res.strategy) strat = res.strategy
      else if (res && res.fields) strat = buildStrategyFromFields(res.fields, jiraId)
      else strat = deriveStrategyFromMarkdown(md)
      setStrategy(strat || '')
    } catch (err) {
      setResult('Error: ' + (err.message || err))
    } finally {
      setLoading(false)
    }
  }

  function deriveStrategyFromMarkdown(md) {
    if (!md) return ''
    // try to extract a '## Strategy' section
    const m = /##\s*Strategy[\s\S]*?\n([\s\S]*?)(?=\n##\s|\n#\s|$)/i.exec(md)
    if (m && m[1]) return m[1].trim()
    // fallback: grab Objective/summary
    const obj = /##\s*Objective\s*\n([\s\S]*?)(?=\n##\s|\n#\s|$)/i.exec(md)
    const summary = obj && obj[1] ? obj[1].split('\n')[0].trim() : ''
    if (summary) return `**Objective:** ${summary}\n\n**Approach:**\n- Investigate reported issue and focus on reproduction and environment matrix.`
    // final fallback: short generic strategy
    return `**Approach:**\n- Investigate issue, reproduce, and document findings.`
  }

  function buildStrategyFromFields(fields, jiraId) {
    if (!fields) return ''
    const summary = fields.summary || ''
    const description = (fields.description || '').split('\n').slice(0,3).join(' ')
    const labels = (fields.labels || []).join(', ')
    return `# Test Strategy: ${jiraId}\n\n**Objective:** ${summary}\n\n**Approach:**\n- Focus on reproducing the reported issue using lightweight exploratory tests.\n- Prioritise browser compatibility checks (Chrome ${labels || 'latest'}, Windows 10) and network/environment permutations.\n\n**Scope & Focus Areas:**\n- UI interaction flows around login (form validation, button click handlers, client-side JS errors).\n- Backend auth endpoints and CORS/network issues if repro suggests requests are sent.\n\n**Entry Criteria:**\n- Access to the JIRA issue and environment details.\n\n**Exit Criteria:**\n- Reproduction steps documented and root-cause hypothesis produced, plus recommended regression checks.\n\n**Notes:**\n- Source: JIRA issue ${jiraId}\n`
  }

  async function handleSave() {
    if (!result) return alert('Nothing to save')
    // Download locally in the browser
    try {
      const blob = new Blob([result], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const filename = (jiraId || 'testplan') + '_Test_Plan.md'
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setSaveStatus(`Downloaded: ${filename}`)
    } catch (err) {
      setSaveStatus('Save error: ' + (err.message || err))
    }
    setTimeout(() => setSaveStatus(''), 5000)
  }

  async function handleSaveStrategy() {
    if (!strategy || !String(strategy).trim()) return alert('No strategy to save')
    try {
      const resp = await saveStrategy(jiraId, strategy)
      setSaveStatus(`Strategy saved: ${resp.path || 'server'}`)
    } catch (err) {
      setSaveStatus('Save strategy error: ' + (err.message || err))
    }
    setTimeout(() => setSaveStatus(''), 5000)
  }

  async function handleDownloadStrategy() {
    if (!strategy || !String(strategy).trim()) return alert('No strategy to download')
    try {
      const blob = new Blob([strategy], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const filename = (jiraId || 'strategy') + '_Test_Strategy.md'
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setSaveStatus(`Downloaded: ${filename}`)
    } catch (err) {
      setSaveStatus('Download strategy error: ' + (err.message || err))
    }
    setTimeout(() => setSaveStatus(''), 5000)
  }

  const planHtml = useMemo(() => {
    if (!result) return '<em>(Press "Generate Test Plan" to create a plan)</em>'
    try {
      let processed = result.replace(/\{\{(https?:\/\/[^}]+)\}\}/g, '[$1]($1)')
      const lines = processed.split(/\r?\n/)
      let stepsIndex = -1
      for (let i = 0; i < lines.length; i++) { if (/steps to reproduce/i.test(lines[i])) { stepsIndex = i; break } }
      if (stepsIndex >= 0) {
        const items = []
        let i = stepsIndex + 1
        for (; i < lines.length; i++) {
          const rawLine = lines[i]
          const line = rawLine.trim()
          if (!line) continue
          const norm = line.replace(/^[>\s*_#-]+/, '').trim()
          if (/^(Expected Result|Actual Result|Environment|Acceptance Criteria|Scope|Strategy|Entry Criteria|Exit Criteria|Risks|Assumptions|Dependencies|Traceability|Sign-off)\b/i.test(norm)) break
          const step = line.replace(/^\s*(?:#+\s+|\d+\.\s+|[-*]\s+)/, '').trim()
          if (step) items.push(step)
        }
        if (items.length) {
          const listHtml = '<div class="tp-steps">' + items.map((s, idx) => {
            let htmlText = ''
            try { htmlText = DOMPurify.sanitize(marked.parseInline(s)) } catch (err) { console.error('parseInline error for step', s, err); htmlText = DOMPurify.sanitize(s) }
            return `<div class="tp-step"><span class="tp-step-num">${idx+1}</span><div class="tp-step-text">${htmlText}</div></div>`
          }).join('') + '</div>'
          const before = lines.slice(0, stepsIndex + 1).join('\n')
          const after = lines.slice(i).join('\n')
          processed = before + '\n\n' + listHtml + '\n\n' + after
        }
      } else {
        processed = processed.replace(/(^|\n)\*\s+/g, '$1- ')
      }
      processed = processed.replace(/\n{3,}/g, '\n\n')
      const renderer = { heading(text, level) { const tag = level === 1 ? 'h2' : level === 2 ? 'h3' : level === 3 ? 'h4' : 'h5'; return `<${tag}>${text}</${tag}>\n` } }
      try { return DOMPurify.sanitize(marked.parse(processed, { renderer })) } catch (err) { console.error('marked.parse error (plan):', err); return '<pre>' + DOMPurify.sanitize(processed) + '</pre>' }
    } catch (e) { return '<pre>' + (result || '') + '</pre>' }
  }, [result])

  const strategyHtml = useMemo(() => {
    if (!strategy) return ''
    try {
      // Normalize and unescape strategy text, then parse to HTML
      let proc = (strategy || '').replace(/\{\{(https?:\/\/[^}]+)\}\}/g, '[$1]($1)')
      // remove fenced code markers and leading/trailing backticks
      proc = proc.replace(/```/g, '')
      proc = proc.replace(/(^\s*`+\s*)|(\s*`+$)/g, '')
      // unescape common HTML entities and numeric/char refs
      proc = proc.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&')
      proc = proc.replace(/&#35;|&num;|\u0023;/g, '#')
      proc = proc.replace(/&#(\d+);/g, (m, d) => String.fromCharCode(Number(d)))
      // Convert common bolded section headers like **Objective:** into markdown headings
      proc = proc.replace(/\*\*\s*Objective\s*:\s*\*\*/gi, '### Objective')
      proc = proc.replace(/\*\*\s*Approach\s*:\s*\*\*/gi, '### Approach')
      proc = proc.replace(/\*\*\s*Scope\s*&?\s*Focus\s*Areas\s*:\s*\*\*/gi, '### Scope & Focus Areas')
      proc = proc.replace(/\*\*\s*Entry Criteria\s*:\s*\*\*/gi, '### Entry Criteria')
      proc = proc.replace(/\*\*\s*Exit Criteria\s*:\s*\*\*/gi, '### Exit Criteria')
      proc = proc.replace(/\*\*\s*Notes\s*:\s*\*\*/gi, '### Notes')
      proc = proc.replace(/\*\*Objective\*\*\s*:/gi, '### Objective:')
      proc = proc.replace(/\*\*Approach\*\*\s*:/gi, '### Approach:')
      proc = proc.replace(/\*\*Scope & Focus Areas\*\*\s*:/gi, '### Scope & Focus Areas:')
      proc = proc.replace(/\n{0,}\s*(### )/g, '\n\n$1')
      // ensure '##' headings are not left escaped or within pre blocks
      proc = proc.replace(/(^|\n)\s*#{2,}\s*/g, '\n\n$&')
      const renderer = { heading(text, level){ const tag = level === 1 ? 'h3' : level ===2 ? 'h4' : 'h5'; return `<${tag}>${text}</${tag}>\n` } }
      try {
        const html = marked.parse(proc, { renderer })
        // Simple line-based converter to guarantee headings/lists render when input contains hashes
        const hasHashes = /(^|\n)\s*#{1,6}\s+/m.test(proc)
        const simpleConverter = (md) => {
          const out = []
          const lines = md.split(/\r?\n/)
          let inList = false
          for (let l of lines) {
            if (/^\s*$/.test(l)) { if (inList) { out.push('</ul>'); inList = false } ; continue }
            const h = /^\s*(#{1,6})\s*(.*)$/.exec(l)
            if (h) { if (inList) { out.push('</ul>'); inList = false } ; const level = Math.min(6, h[1].length); out.push(`<h${level}>${DOMPurify.sanitize(h[2])}</h${level}>`); continue }
            const li = /^\s*[-*+]\s+(.*)$/.exec(l)
            if (li) { if (!inList) { out.push('<ul>'); inList = true } ; out.push(`<li>${DOMPurify.sanitize(li[1])}</li>`); continue }
            if (inList) { out.push('</ul>'); inList = false }
            out.push(`<p>${DOMPurify.sanitize(l)}</p>`)
          }
          if (inList) out.push('</ul>')
          return out.join('\n')
        }
        if (hasHashes) {
          try { return DOMPurify.sanitize(simpleConverter(proc)) } catch (e) { /* fallthrough */ }
        }
        // If marked didn't transform the markdown (still shows raw hashes or backticks),
        // apply a simple, safe line-based converter as a robust fallback.
        const looksRaw = /(^|\n)\s*[`]{1,3}|(^|\n)\s*#{1,6}\s+/m
        if (looksRaw.test(proc) && (!/<(h|p|ul|ol|div)/i.test(html) || /`{1,3}/.test(proc))) {
          const simple = (md) => {
            const out = []
            const lines = md.split(/\r?\n/)
            let inList = false
            for (let l of lines) {
              if (/^\s*$/i.test(l)) {
                if (inList) { out.push('</ul>'); inList = false }
                continue
              }
              const h = /^\s*(#{1,6})\s*(.*)$/.exec(l)
              if (h) {
                if (inList) { out.push('</ul>'); inList = false }
                const level = Math.min(6, h[1].length)
                out.push(`<h${level}>${DOMPurify.sanitize(h[2])}</h${level}>`)
                continue
              }
              const li = /^\s*[-*+]\s+(.*)$/.exec(l)
              if (li) {
                if (!inList) { out.push('<ul>'); inList = true }
                out.push(`<li>${DOMPurify.sanitize(li[1])}</li>`)
                continue
              }
              // default paragraph line
              if (inList) { out.push('</ul>'); inList = false }
              out.push(`<p>${DOMPurify.sanitize(l)}</p>`)
            }
            if (inList) out.push('</ul>')
            return out.join('\n')
          }
          try {
            return simple(proc)
          } catch (e) {
            return DOMPurify.sanitize(html)
          }
        }
        return DOMPurify.sanitize(html)
      } catch (err) {
        console.error('marked.parse error (strategy):', err)
        return '<pre>' + DOMPurify.sanitize(proc) + '</pre>'
      }
    } catch (err) { return '<pre>' + (strategy || '') + '</pre>' }
  }, [strategy])

  return (
    <ErrorBoundary>
      <div className="container">
        <div className="card">
          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:12}}>
            <h1>{viewMode === 'plan' ? 'Test Plan Generator' : 'Test Strategy Generator'}</h1>
            <div>
              <button className={"btn-ghost"} style={{marginRight:8}} onClick={()=>setViewMode('plan')}>Plan</button>
              <button className={"btn-ghost"} style={{marginRight:8}} onClick={()=>setViewMode('strategy')}>Strategy</button>
              <button className={"btn-ghost"} onClick={()=>setViewMode('both')}>Both</button>
            </div>
          </div>
          <div className="toolbar" role="toolbar" aria-label="Generator controls">
            <button className="btn-ghost" onClick={saveSettings}>Save Settings</button>
            {viewMode === 'plan' ? (
              <>
                <button className="btn-primary" onClick={() => handleGenerate()}>{loading ? 'Generating...' : 'Generate Test Plan'}</button>
                <button className="btn-ghost" onClick={handleSave}>Save To File</button>
              </>
            ) : viewMode === 'strategy' ? (
              <>
                <button className="btn-primary" onClick={() => handleGenerate()}>{loading ? 'Generating...' : 'Generate Strategy'}</button>
                <button className="btn-ghost" onClick={handleSaveStrategy}>Save Strategy</button>
                <button className="btn-ghost" onClick={handleDownloadStrategy}>Download Strategy</button>
              </>
            ) : (
              <>
                <button className="btn-primary" onClick={() => handleGenerate()}>{loading ? 'Generating...' : 'Generate Both'}</button>
                <button className="btn-ghost" onClick={handleSave}>Save Test Plan</button>
                <button className="btn-ghost" onClick={handleSaveStrategy}>Save Strategy</button>
                <button className="btn-ghost" onClick={handleDownloadStrategy}>Download Strategy</button>
              </>
            )}
          </div>
          {viewMode === 'strategy' ? (
            <div style={{background:'rgba(255,242,230,0.6)',padding:12,borderRadius:8,marginTop:8}}>
              <strong>Test Strategy — purpose & fields</strong>
              <p className="small">The Test Strategy focuses the testing approach for the issue. It includes:</p>
              <ul className="small">
                <li><strong>Objective</strong>: short summary of what to validate.</li>
                <li><strong>Approach</strong>: how to reproduce, exploratory vs scripted, priority checks.</li>
                <li><strong>Scope & Focus Areas</strong>: which modules, browsers, environments.</li>
                <li><strong>Entry / Exit Criteria</strong>: when testing starts and what qualifies completion.</li>
                <li><strong>Notes</strong>: environment, assumptions, and traceability.</li>
              </ul>
              <p className="small">This UI derives Strategy automatically from the JIRA fields or the generated Test Plan. You can edit, download or save it.</p>
            </div>
          ) : null}
          {(viewMode === 'strategy' || viewMode === 'both') ? (
            <div style={{marginTop:12}}>
              <label>Strategy (editable)</label>
              <textarea style={{width:'100%',minHeight:120}} value={strategy} onChange={e=>setStrategy(e.target.value)} />
            </div>
          ) : null}
        <form onSubmit={handleGenerate}>
          <label>JIRA Base URL</label>
          <input value={jiraBaseUrl} onChange={e => setJiraBaseUrl(e.target.value)} placeholder="https://yourcompany.atlassian.net" />

          <label>JIRA Email</label>
          <input value={jiraEmail} onChange={e => setJiraEmail(e.target.value)} />

          <label>JIRA API Token</label>
          <input value={jiraToken} onChange={e => setJiraToken(e.target.value)} />

          <label>GROQ API URL</label>
          <input value={groqUrl} onChange={e => setGroqUrl(e.target.value)} placeholder="https://api.groq..." />

          <label>GROQ API Key</label>
          <input value={groqKey} onChange={e => setGroqKey(e.target.value)} />

          <label>JIRA ID</label>
          <input value={jiraId} onChange={e => setJiraId(e.target.value)} />

          <label style={{marginTop:8}} className="small"><input type="checkbox" checked={useGroq} onChange={e=>setUseGroq(e.target.checked)} /> Use GROQ/OpenGPT (otherwise uses local generator)</label>

          <div className="controls">
            <button type="button" className="btn-ghost" onClick={saveSettings}>Save Settings</button>
            {viewMode === 'plan' ? (
              <>
                <button type="submit" className="btn-primary">{loading ? 'Generating...' : 'Generate Test Plan'}</button>
                <button type="button" className="btn-ghost" onClick={handleSave}>Save To File</button>
              </>
            ) : (
              <>
                <button type="button" className="btn-primary" onClick={() => handleGenerate()}>{loading ? 'Generating...' : 'Generate Strategy'}</button>
                <button type="button" className="btn-ghost" onClick={handleSaveStrategy}>Save Strategy</button>
                <button type="button" className="btn-ghost" onClick={handleDownloadStrategy}>Download Strategy</button>
              </>
            )}
          </div>
        </form>

        <section>
          {viewMode === 'plan' || viewMode === 'both' ? (
            <>
              <h2 className="section-title">Generated Test Plan (Preview)</h2>
              <div className="output" dangerouslySetInnerHTML={{ __html: planHtml }} />
            </>
          ) : null}

          {viewMode === 'strategy' || viewMode === 'both' ? (
            <>
              <h2 className="section-title">Generated Test Strategy (Preview)</h2>
              <div className="output" dangerouslySetInnerHTML={{ __html: strategyHtml }} />
            </>
          ) : null}
          <div className="footer">{saveStatus}</div>
        </section>
        </div>
      </div>
    </ErrorBoundary>
  )
}

