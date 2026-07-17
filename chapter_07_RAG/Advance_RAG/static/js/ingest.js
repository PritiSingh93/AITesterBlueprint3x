// Ingest page: consume the SSE stream and render per-stage cards.
const params = new URLSearchParams(location.search);
const startBtn = document.getElementById('startBtn');
const cards = document.getElementById('stageCards');
const ORDER = ['read', 'build', 'chunk', 'embed', 'index'];

function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

function markStage(stage, state) {
  const el = document.querySelector(`#stageTracker .stage[data-stage="${stage}"]`);
  if (!el) return;
  const idx = ORDER.indexOf(stage);
  if (state === 'done') {
    el.classList.remove('active'); el.classList.add('done');
  } else if (state === 'active') {
    ORDER.slice(0, idx).forEach(s => document.querySelector(`.stage[data-stage="${s}"]`)?.classList.add('done'));
    el.classList.add('active');
  }
}

function card(stage) {
  let el = document.getElementById('card-' + stage);
  if (!el) {
    el = document.createElement('div');
    el.className = 'card reveal';
    el.id = 'card-' + stage;
    cards.appendChild(el);
  }
  return el;
}

startBtn.addEventListener('click', () => {
  startBtn.disabled = true;
  startBtn.innerHTML = '<span class="spinner"></span> Running…';
  cards.innerHTML = '';
  const q = new URLSearchParams();
  if (params.get('text_cols')) q.set('text_cols', params.get('text_cols'));
  if (params.get('meta_cols')) q.set('meta_cols', params.get('meta_cols'));
  const es = new EventSource('/api/ingest/stream?' + q.toString());

  es.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    handle(ev);
    if (ev.stage === 'complete' || ev.stage === 'error') {
      es.close();
      startBtn.disabled = false;
      startBtn.innerHTML = ev.stage === 'error' ? '↻ Retry' : '✓ Done — re-run';
      if (typeof refreshStatus === 'function') refreshStatus();
    }
  };
  es.onerror = () => { es.close(); startBtn.disabled = false; startBtn.innerHTML = '↻ Retry'; };
});

function handle(ev) {
  const { stage, status, data, message } = ev;
  if (stage === 'error') {
    card('error').innerHTML = `<h3 style="color:var(--err)">Error</h3><p class="small">${esc(message || '')}</p>`;
    return;
  }
  if (stage === 'start') return;
  if (status === 'running') markStage(stage, 'active');
  if (status === 'done' && stage !== 'complete') markStage(stage, 'done');

  if (stage === 'read' && status === 'done') {
    card('read').innerHTML = `<h3>1 · Read</h3>
      <div class="grid-3">
        <div class="stat"><div class="n">${data.rows.toLocaleString()}</div><div class="k">rows parsed</div></div>
        <div class="stat"><div class="n">${data.text_cols.length}</div><div class="k">text columns</div></div>
        <div class="stat"><div class="n">${data.meta_cols.length}</div><div class="k">metadata columns</div></div>
      </div>
      <p class="flow-note">Text: ${data.text_cols.map(c => `<span class="badge coral">${esc(c)}</span>`).join(' ')}
       &nbsp;·&nbsp; Meta: ${data.meta_cols.map(c => `<span class="badge">${esc(c)}</span>`).join(' ')}</p>`;
  }
  if (stage === 'build' && status === 'done') {
    card('build').innerHTML = `<h3>2 · Build documents</h3>
      <p class="sub">Each row's text columns are concatenated into one document.</p>
      <div class="chunk-text">${esc(data.sample)}${data.sample.length >= 500 ? '…' : ''}</div>`;
  }
  if (stage === 'chunk' && status === 'done') {
    card('chunk').innerHTML = renderChunk(data);
    requestAnimationFrame(() => animateHisto(data.histogram));
  }
  if (stage === 'embed') {
    renderEmbed(status, data);
  }
  if (stage === 'index') {
    renderIndex(status, data);
  }
  if (stage === 'complete') {
    card('complete').innerHTML = `<h3 style="color:var(--ok)">✓ Ingestion complete</h3>
      <p class="sub">${data.chunks.toLocaleString()} chunks indexed in ${data.elapsed}s.</p>
      <a class="btn" href="/chunks">Browse chunks →</a>
      <a class="btn soft" href="/chat">Go to chat →</a>`;
  }
}

function renderChunk(d) {
  const samples = d.samples.map((s, i) => {
    let html = esc(s.text);
    if (s.overlap > 0) {
      const ov = esc(s.text.slice(0, s.overlap));
      html = '<mark>' + ov + '</mark>' + esc(s.text.slice(s.overlap));
    }
    return `<div style="margin-top:10px"><div class="small muted">${esc(s.id)}${s.overlap ? ' · <b style="color:var(--coral-deep)">' + s.overlap + ' chars overlap</b> from previous' : ''}</div>
      <div class="chunk-text">${html}${s.text.length >= 600 ? '…' : ''}</div></div>`;
  }).join('');
  return `<h3>3 · Chunk</h3>
    <p class="sub">1 row = 1 chunk when small; larger docs split with overlap (coral = repeated text).</p>
    <div class="grid-3">
      <div class="stat"><div class="n">${d.total.toLocaleString()}</div><div class="k">total chunks</div></div>
      <div class="stat"><div class="n">${d.avg}</div><div class="k">avg chars</div></div>
      <div class="stat"><div class="n">${d.min}–${d.max}</div><div class="k">min–max chars</div></div>
    </div>
    <h4 style="margin:16px 0 0;font-size:12px;color:var(--ink-faint);text-transform:uppercase;letter-spacing:.05em">Chunk-length distribution</h4>
    <div class="histo" id="histo"></div>
    <div class="histo-axis"><span>${d.histogram.edges[0]}</span><span>${d.histogram.edges[d.histogram.edges.length - 1]} chars</span></div>
    ${samples}`;
}

function animateHisto(h) {
  const wrap = document.getElementById('histo');
  if (!wrap) return;
  const max = Math.max(...h.buckets, 1);
  wrap.innerHTML = h.buckets.map(b => `<div class="bar" style="height:0"><span>${b || ''}</span></div>`).join('');
  requestAnimationFrame(() => {
    [...wrap.children].forEach((bar, i) => { bar.style.height = (6 + (h.buckets[i] / max) * 84) + 'px'; });
  });
}

function renderEmbed(status, d) {
  const el = card('embed');
  const dense = (d.dense_preview || []).map(v => {
    const h = 6 + Math.abs(v) * 60;
    return `<span style="height:${Math.min(44, h)}px" title="${v}"></span>`;
  }).join('');
  const sparse = (d.sparse_top || []).map(([t, w]) => `<span class="tok">${esc(t)}<b>${w}</b></span>`).join('');
  const pct = d.total ? Math.round((d.done / d.total) * 100) : 0;
  el.innerHTML = `<h3>4 · Embed <span class="badge coral">${esc(d.model || d.backend || '')}</span></h3>
    <p class="sub">Every chunk becomes a dense semantic vector + a sparse lexical vector.</p>
    <div class="progress"><i style="width:${pct}%"></i></div>
    <p class="flow-note">${(d.done || 0).toLocaleString()} / ${(d.total || 0).toLocaleString()} chunks embedded (${pct}%)</p>
    ${dense ? `<h4 style="margin:14px 0 4px;font-size:12px;color:var(--ink-faint);text-transform:uppercase;letter-spacing:.05em">Dense vector · first 8 of ${d.dense_dim} dims</h4>
      <div class="dense-bars">${dense}</div>` : ''}
    ${sparse ? `<h4 style="margin:14px 0 4px;font-size:12px;color:var(--ink-faint);text-transform:uppercase;letter-spacing:.05em">Sparse · top tokens by weight</h4>
      <div class="sparse-tokens">${sparse}</div>` : ''}`;
}

function renderIndex(status, d) {
  const el = card('index');
  if (status === 'progress') {
    const pct = d.total ? Math.round((d.done / d.total) * 100) : 0;
    el.innerHTML = `<h3>5 · Index into Qdrant</h3>
      <div class="progress"><i style="width:${pct}%"></i></div>
      <p class="flow-note">${(d.done || 0).toLocaleString()} / ${(d.total || 0).toLocaleString()} points upserted</p>`;
  } else if (status === 'done') {
    const c = d.collection || {};
    el.innerHTML = `<h3>5 · Index into Qdrant <span class="badge sage">done</span></h3>
      <div class="grid-2">
        <div class="stat"><div class="n">${(c.points || 0).toLocaleString()}</div><div class="k">points in '${esc(c.name || '')}'</div></div>
        <div class="stat"><div class="n">${d.elapsed}s</div><div class="k">total ingest time</div></div>
      </div>
      <p class="flow-note">Vectors: ${(c.vectors || []).map(v => `<span class="badge coral">${esc(v)}</span>`).join(' ')}<br>
        Storage: <span class="badge">${esc(c.storage || '')}</span></p>`;
  }
}

// Auto-start if we arrived straight from the column picker.
if (params.get('text_cols')) startBtn.click();
