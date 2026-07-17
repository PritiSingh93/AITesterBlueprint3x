// Upload page: file pick -> preview -> column picker -> kick off ingest.
const dz = document.getElementById('dropzone');
const input = document.getElementById('fileInput');
const statusEl = document.getElementById('uploadStatus');
const previewArea = document.getElementById('previewArea');

dz.addEventListener('click', () => input.click());
['dragover', 'dragenter'].forEach(ev => dz.addEventListener(ev, e => {
  e.preventDefault(); dz.style.borderColor = 'var(--coral)'; dz.style.background = 'var(--coral-wash)';
}));
['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => {
  e.preventDefault(); dz.style.borderColor = 'var(--line-2)'; dz.style.background = 'transparent';
}));
dz.addEventListener('drop', e => { if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]); });
input.addEventListener('change', () => { if (input.files[0]) upload(input.files[0]); });

function setStage(name) {
  document.querySelectorAll('#stageTracker .stage').forEach(s => {
    const order = ['upload', 'columns', 'ingest'];
    const idx = order.indexOf(s.dataset.stage);
    const cur = order.indexOf(name);
    s.classList.toggle('done', idx < cur);
    s.classList.toggle('active', idx === cur);
  });
}

async function upload(file) {
  statusEl.style.display = 'block';
  statusEl.innerHTML = '<span class="spinner"></span> Reading <b>' + file.name + '</b>…';
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/api/upload', { method: 'POST', body: fd });
  const data = await res.json();
  if (!res.ok) { statusEl.innerHTML = '⚠️ ' + (data.error || 'Upload failed'); return; }
  statusEl.innerHTML = '✅ Loaded <b>' + file.name + '</b> — ' + data.preview.rows.toLocaleString() + ' rows × ' + data.preview.cols + ' columns';
  setStage('columns');
  renderPreview(data);
}

function renderPreview(data) {
  const p = data.preview;
  const cols = p.columns;
  const textSet = new Set(data.suggested_text_cols);
  const metaSet = new Set(data.suggested_meta_cols);

  const colRows = cols.map(c => `
    <tr>
      <td><b>${esc(c)}</b> <span class="muted small">${esc(p.dtypes[c] || '')}</span></td>
      <td style="text-align:center"><input type="checkbox" class="text-col" value="${esc(c)}" ${textSet.has(c) ? 'checked' : ''}></td>
      <td style="text-align:center"><input type="checkbox" class="meta-col" value="${esc(c)}" ${metaSet.has(c) ? 'checked' : ''}></td>
    </tr>`).join('');

  const headCols = cols.slice(0, 6);
  const headRows = p.head.map(r => '<tr>' + headCols.map(c => `<td>${esc(String(r[c] ?? '')).slice(0, 90)}</td>`).join('') + '</tr>').join('');

  previewArea.innerHTML = `
    <div class="card reveal">
      <h3>Choose columns</h3>
      <p class="sub">Text columns are concatenated into the embedded document. Metadata columns
        are stored in the Qdrant payload for filtering on the Chunks &amp; Chat pages.</p>
      <div class="scroll-x">
        <table>
          <thead><tr><th>Column</th><th style="text-align:center">Embed (text)</th><th style="text-align:center">Metadata</th></tr></thead>
          <tbody>${colRows}</tbody>
        </table>
      </div>
      <div style="margin-top:16px;display:flex;gap:10px;align-items:center">
        <button class="btn" id="goIngest">Continue to ingest →</button>
        <span class="muted small">This will embed every row and (re)build the collection.</span>
      </div>
    </div>
    <div class="card reveal">
      <h3>First 5 rows</h3>
      <div class="scroll-x">
        <table><thead><tr>${headCols.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead>
        <tbody>${headRows}</tbody></table>
      </div>
    </div>`;

  document.getElementById('goIngest').addEventListener('click', () => {
    const text = [...document.querySelectorAll('.text-col:checked')].map(x => x.value);
    const meta = [...document.querySelectorAll('.meta-col:checked')].map(x => x.value);
    if (!text.length) { alert('Pick at least one text column to embed.'); return; }
    setStage('ingest');
    const q = new URLSearchParams({ text_cols: text.join(','), meta_cols: meta.join(',') });
    location.href = '/ingest?' + q.toString();
  });
}

function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
