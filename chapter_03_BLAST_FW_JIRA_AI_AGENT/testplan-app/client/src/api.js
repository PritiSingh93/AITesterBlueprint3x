export async function generateTestPlan(payload) {
  const res = await fetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  if (!res.ok) {
    const txt = await res.text()
    let body = txt
    try { body = JSON.parse(txt) } catch (e) {}
    const err = new Error('Request failed: ' + res.status + ' ' + res.statusText)
    err.status = res.status
    err.body = body
    throw err
  }
  return res.json()
}

export async function saveTestPlan(jiraId, markdown) {
  const res = await fetch('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jiraId, markdown })
  })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(txt || 'Save failed')
  }
  return res.json()
}

export async function saveStrategy(jiraId, strategy) {
  const res = await fetch('/api/save-strategy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jiraId, strategy })
  })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(txt || 'Save strategy failed')
  }
  return res.json()
}
