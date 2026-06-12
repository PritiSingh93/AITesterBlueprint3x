import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'

function showOverlayError(msg) {
  try {
    const existing = document.getElementById('global-error-overlay')
    if (existing) existing.remove()
    const o = document.createElement('div')
    o.id = 'global-error-overlay'
    Object.assign(o.style, {position:'fixed',inset:0,background:'rgba(0,0,0,0.6)',color:'#fff',padding:20,zIndex:9999,overflow:'auto'})
    o.innerHTML = `<h2 style="color:#ffd08a">Application error</h2><pre style="white-space:pre-wrap;color:#fff">${String(msg)}</pre>`
    document.body.appendChild(o)
  } catch (e) { console.error('overlay failed', e) }
}

window.addEventListener('error', (ev) => {
  console.error('Global error:', ev.error || ev.message || ev)
  showOverlayError(ev.error ? (ev.error.stack || ev.error.message) : (ev.message || String(ev)))
})
window.addEventListener('unhandledrejection', (ev) => {
  console.error('Unhandled rejection:', ev.reason)
  showOverlayError(ev.reason && ev.reason.stack ? ev.reason.stack : String(ev.reason))
})

const rootEl = document.getElementById('root')
if (!rootEl) {
  document.body.innerHTML = '<div style="padding:20px">Missing <code>div#root</code> in index.html — cannot mount app.</div>'
} else {
  try {
    createRoot(rootEl).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    )
  } catch (err) {
    console.error('Render failed:', err)
    showOverlayError(err.stack || err.message || String(err))
  }
}
