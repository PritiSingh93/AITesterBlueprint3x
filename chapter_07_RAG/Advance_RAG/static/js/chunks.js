// Chunks browser: paginated viewer with filters + last-context highlight.
let page = 1;
const PAGE_SIZE = 50;
const listEl = document.getElementById('chunkList');
const pagerEl = document.getElementById('pager');
const pagerBottom = document.getElementById('pagerBottom');

function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

async function loadFilters() {
  try {
    const f = await (await fetch('/api/chunks/filters')).json();
    fill('fPriority', f.priority || []);
    fill('fModule', f.module || []);
  } catch (e) {}
}
function fill(id, values) {
  const sel = document.getElementById(id);
  values.forEach(v => { const o = document.createElement('option'); o.value = v; o.textContent = v; sel.appendChild(o); });
}

function currentFilters() {
  return {
    q: document.getElementById('search').value.trim(),
    priority: document.getElementById('fPriority').value,
    module: document.getElementById('fModule').value,
    jira_id: document.getElementById('fJira').value.trim(),
  };
}

async function load() {
  listEl.innerHTML = '<div class="empty"><span class="spinner"></span> Loading chunks…</div>';
  const f = currentFilters();
  const q = new URLSearchParams({ page, page_size: PAGE_SIZE, ...f });
  const data = await (await fetch('/api/chunks?' + q)).json();

  if (!data.chunks || !data.chunks.length) {
    listEl.innerHTML = `<div class="empty">${data.collection_total ? 'No chunks match these filters.' : 'Nothing ingested yet. <a href="/upload">Upload a CSV</a> to begin.'}</div>`;
    pagerEl.textContent = ''; pagerBottom.innerHTML = '';
    return;
  }
  const ctx = new Set(data.last_context || []);
  listEl.innerHTML = data.chunks.map(c => renderChunk(c, ctx.has(c.id))).join('');
  pagerEl.textContent = `Page ${data.page} · ${data.collection_total.toLocaleString()} chunks total`;
  renderPager(data.has_more);
}

function renderChunk(c, highlighted) {
  const p = c.payload || {};
  const badges = [];
  if (p.priority) badges.push(`<span class="badge ${esc(p.priority)}">${esc(p.priority)}</span>`);
  if (p.module) badges.push(`<span class="badge">${esc(p.module)}</span>`);
  if (p.jira_id) badges.push(`<span class="badge blue">${esc(p.jira_id)}</span>`);
  const tags = (p.tags || '').split(';').filter(Boolean).map(t => `<span class="tok">${esc(t)}</span>`).join(' ');
  return `<div class="card${highlighted ? '' : ''}" style="${highlighted ? 'border:2px solid var(--coral);box-shadow:0 0 0 4px var(--coral-wash)' : ''}">
    <div style="display:flex;justify-content:space-between;gap:10px;align-items:baseline;flex-wrap:wrap">
      <h3 style="margin:0">${esc(p.title || p.chunk_id || c.id)}</h3>
      <span class="mono small muted">${esc(c.id)}${highlighted ? ' · <b style="color:var(--coral-deep)">used in last answer</b>' : ''}</span>
    </div>
    <p style="margin:6px 0 8px">${badges.join(' ')}</p>
    ${tags ? `<div class="sparse-tokens" style="margin-bottom:8px">${tags}</div>` : ''}
    <div class="chunk-text">${esc(c.text)}</div>
  </div>`;
}

function renderPager(hasMore) {
  const mk = (label, disabled, fn) => {
    const b = document.createElement('button');
    b.className = 'btn soft'; b.textContent = label; b.disabled = disabled;
    b.addEventListener('click', fn); return b;
  };
  pagerBottom.innerHTML = '';
  pagerBottom.appendChild(mk('← Prev', page <= 1, () => { page--; load(); scrollTo(0, 0); }));
  const info = document.createElement('span'); info.className = 'pill'; info.textContent = 'Page ' + page;
  pagerBottom.appendChild(info);
  pagerBottom.appendChild(mk('Next →', !hasMore, () => { page++; load(); scrollTo(0, 0); }));
}

document.getElementById('applyBtn').addEventListener('click', () => { page = 1; load(); });
document.getElementById('search').addEventListener('keydown', e => { if (e.key === 'Enter') { page = 1; load(); } });
loadFilters();
load();
