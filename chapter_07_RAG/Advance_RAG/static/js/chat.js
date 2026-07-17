// Chat page: run the query pipeline, animate the stage tracker, render the trace.
const log = document.getElementById('chatLog');
const qInput = document.getElementById('q');
const sendBtn = document.getElementById('sendBtn');
const STAGES = ['rewrite', 'search', 'fuse', 'rerank', 'generate'];

function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

function resetStages() {
  document.querySelectorAll('#stageTracker .stage').forEach(s => s.classList.remove('active', 'done'));
}
function setStage(name, done) {
  const idx = STAGES.indexOf(name);
  STAGES.forEach((s, i) => {
    const el = document.querySelector(`.stage[data-stage="${s}"]`);
    if (!el) return;
    el.classList.toggle('done', i < idx || (i === idx && done));
    el.classList.toggle('active', i === idx && !done);
  });
}
// Animate the tracker while the request is in flight (purely cosmetic pacing).
function runStageAnimation() {
  let i = 0;
  setStage(STAGES[0], false);
  const t = setInterval(() => {
    i++;
    if (i >= STAGES.length) { clearInterval(t); return; }
    setStage(STAGES[i], false);
  }, 420);
  return () => { clearInterval(t); STAGES.forEach(s => setStage(s, true)); setStage('generate', true); };
}

function citeify(text) {
  return esc(text).replace(/\[Chunk\s*(\d+)\]/gi, '<span class="cite">[Chunk $1]</span>')
                  .replace(/\n/g, '<br>');
}

async function ask(question) {
  document.getElementById('emptyState')?.remove();
  addUser(question);
  const placeholder = addAssistantLoading();
  resetStages();
  const finish = runStageAnimation();

  let data;
  try {
    const res = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    data = await res.json();
  } catch (e) {
    data = { error: 'Request failed: ' + e.message };
  }
  finish();
  placeholder.remove();

  if (data.error) { addAssistant(`<p style="color:var(--err)">⚠️ ${esc(data.error)}</p>`); return; }
  renderAnswer(data);
  updateLastMode(data);
  scrollBottom();
}

function addUser(text) {
  const el = document.createElement('div');
  el.className = 'msg user';
  el.innerHTML = `<div class="bubble">${esc(text)}</div>`;
  log.appendChild(el); scrollBottom();
}
function addAssistantLoading() {
  const el = document.createElement('div');
  el.className = 'msg assistant';
  el.innerHTML = `<div class="bubble"><span class="spinner"></span> <span class="muted">rewriting → searching → fusing → re-ranking → generating…</span></div>`;
  log.appendChild(el); scrollBottom();
  return el;
}
function addAssistant(html) {
  const el = document.createElement('div');
  el.className = 'msg assistant';
  el.innerHTML = `<div class="bubble">${html}</div>`;
  log.appendChild(el); scrollBottom();
  return el;
}

function renderAnswer(d) {
  const modeBadge = d.mode === 'generate'
    ? '<span class="badge coral">Generate mode</span>'
    : '<span class="badge sage">Answer mode</span>';
  const html = `
    <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap">
      ${modeBadge}
      <span class="small muted">${d.elapsed}s · ${d.backend === 'real' ? 'bge-m3' : 'lite'} · ${d.groq ? 'groq' : 'fallback'}</span>
    </div>
    <div class="answer" style="margin-top:10px">${citeify(d.answer || '')}</div>
    ${renderTrace(d)}`;
  addAssistant(html);
}

function renderTrace(d) {
  const rw = (d.rewrites || []).map((r, i) => `<div class="rw"><b>#${i + 1}</b>${esc(r)}</div>`).join('');
  const listTable = (rows, cols) => `<div class="scroll-x"><table><thead><tr>${cols.map(c => `<th>${c[0]}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r => '<tr>' + cols.map(c => `<td>${c[1](r)}</td>`).join('') + '</tr>').join('')}</tbody></table></div>`;

  const dense = listTable((d.dense_top || []).slice(0, 8), [
    ['#', (_, i) => ''], ['Jira', r => `<span class="mono">${esc(r.jira_id || '')}</span>`],
    ['Title', r => esc((r.title || '').slice(0, 60))], ['Score', r => `<b>${r.score}</b>`]]);
  const sparse = listTable((d.sparse_top || []).slice(0, 8), [
    ['Jira', r => `<span class="mono">${esc(r.jira_id || '')}</span>`],
    ['Title', r => esc((r.title || '').slice(0, 60))], ['Score', r => `<b>${r.score}</b>`]]);
  const fused = listTable((d.fused_top || []).slice(0, 8), [
    ['Jira', r => `<span class="mono">${esc(r.jira_id || '')}</span>`],
    ['Title', r => esc((r.title || '').slice(0, 55))],
    ['d-rank', r => r.dense_rank ?? '—'], ['s-rank', r => r.sparse_rank ?? '—'],
    ['RRF', r => `<b>${r.rrf ?? ''}</b>`]]);

  // Re-rank before/after: mark rows that changed position.
  const before = d.rerank?.before || [];
  const after = d.rerank?.after || [];
  const beforeIds = before.map(x => x.id);
  const rerank = `<div class="grid-2">
    <div><h4>Before (RRF order)</h4>${listTable(before.slice(0, 6), [
      ['#', (_, i) => ''], ['Title', r => esc((r.title || '').slice(0, 45))], ['RRF', r => r.rrf]])}</div>
    <div><h4>After (cross-encoder)</h4>${listTableMoved(after.slice(0, 6), beforeIds)}</div>
  </div>`;

  const ctx = (d.context || []).map((c, i) => `
    <div style="margin-top:8px">
      <div class="small"><b class="cite">[Chunk ${i + 1}]</b> <span class="mono muted">${esc(c.id)}</span>
        <span class="badge coral" style="margin-left:6px">rerank ${c.score}</span></div>
      <div class="chunk-text" style="max-height:150px">${esc(c.text)}</div>
    </div>`).join('');

  return `<details class="trace"><summary>Pipeline trace</summary><div class="trace-body">
    <div class="trace-section"><h4>1 · Query rewrites (${(d.rewrites || []).length})</h4><div class="rewrites">${rw}</div></div>
    <div class="trace-section"><h4>2 · Hybrid search — dense vs sparse (top 8 each)</h4>
      <div class="grid-2"><div><h4>Dense (semantic)</h4>${dense}</div><div><h4>Sparse (lexical)</h4>${sparse}</div></div></div>
    <div class="trace-section"><h4>3 · RRF fusion (top 8)</h4>${fused}</div>
    <div class="trace-section"><h4>4 · Re-rank — cross-encoder reorder</h4>${rerank}</div>
    <div class="trace-section"><h4>5 · Context sent to the LLM (top ${(d.context || []).length})</h4>${ctx}</div>
  </div></details>`;
}

function listTableMoved(rows, beforeIds) {
  return `<div class="scroll-x"><table><thead><tr><th>#</th><th>Title</th><th>Score</th></tr></thead><tbody>${
    rows.map((r, i) => {
      const wasAt = beforeIds.indexOf(r.id);
      const moved = wasAt !== i;
      return `<tr class="${moved ? 'moved' : ''}"><td>${moved && wasAt >= 0 ? `${wasAt + 1}→${i + 1}` : i + 1}</td>
        <td>${esc((r.title || '').slice(0, 45))}</td><td><b>${r.score}</b></td></tr>`;
    }).join('')}</tbody></table></div>`;
}

function updateLastMode(d) {
  const el = document.getElementById('lastMode');
  if (!el) return;
  el.innerHTML = `<div class="card"><h3>Last query</h3>
    <p class="small muted">Mode: <b>${d.mode}</b> · ${(d.rewrites || []).length} rewrites ·
    ${(d.context || []).length} chunks · ${d.elapsed}s</p></div>`;
}

function scrollBottom() { log.scrollTop = log.scrollHeight; }

sendBtn.addEventListener('click', send);
qInput.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });
function send() {
  const q = qInput.value.trim();
  if (!q) return;
  qInput.value = '';
  ask(q);
}
document.addEventListener('click', e => {
  if (e.target.classList.contains('ex')) { e.preventDefault(); qInput.value = e.target.textContent; send(); }
});
