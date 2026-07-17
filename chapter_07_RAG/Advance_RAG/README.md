# Advanced RAG Explorer

End-to-end teaching demo for **The Testing Academy**. Upgrades `Basic_RAG`
with the techniques that matter at scale on a real corpus (**2,000 VWO test
cases**, in [`testcase/VWO_2000_Test_Cases.csv`](testcase/VWO_2000_Test_Cases.csv)):

- **Hybrid retrieval** — `bge-m3` produces dense + sparse vectors from one model
- **Vector DB** — Qdrant, **embedded by default** (local file store, no Docker)
- **Re-ranking** — `BAAI/bge-reranker-v2-m3` cross-encoder
- **Query rewriting** — alternate phrasings via Groq before retrieval
- **Generation** — Groq `openai/gpt-oss-120b` (same as Basic)

The UI uses a cool light-grey theme with a steel-blue accent, in a two-pane
layout: **left** = pipeline stage tracker (live), **right** = active content / chat.

> **Runs on any laptop.** If `FlagEmbedding`/`torch` aren't installed (or you set
> `RAG_LITE=1`), the app transparently falls back to a **dependency-free local
> backend** — hashing dense+sparse embeddings + a lexical reranker. Every stage
> looks and behaves the same; only the model quality differs. Install the real
> models for production-grade retrieval.

---

## Pipeline

```
Stage 1 (Ingest):
  CSV/XLSX -> rows -> assemble docs -> chunk (1 row = 1 chunk if small) ->
  bge-m3 (dense + sparse) -> Qdrant collection 'vwo_test_cases'

Stage 2 (Chat):
  Question -> rewrite (Groq) -> embed -> dense + sparse search ->
  RRF fuse -> bge-reranker-v2-m3 -> Groq -> grounded answer
```

---

## Setup

```bash
cd chapter_07_RAG/Advance_RAG
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
```

Qdrant runs **embedded** by default (file store at `./qdrant_data/`) — no Docker
required. To use a Qdrant server instead, set `QDRANT_URL=http://host:6333` in `.env`.

`.env` is pre-populated with the same `GROQ_API_KEY` as Basic.

---

## Run

```bash
python app.py
# open http://127.0.0.1:5050
```

With the real models, the first request hits cold loaders (bge-m3 ~2.3 GB,
bge-reranker ~570 MB the first time from the HF cache) — subsequent requests are
fast. In lite mode there is no download and the first request is instant.

### CLI ingestion (optional)

```bash
python ingest.py testcase/VWO_2000_Test_Cases.csv \
  --text-cols title,steps,expected,tags \
  --meta-cols id,jira_id,priority,module
```

---

## What you can see in the UI

### `/upload`
- File picker accepts `.csv`, `.xlsx`, `.xls`.
- After upload: row count, columns, first 5 rows, dtypes.
- Pick **text columns** (concatenated into the embedded document) and
  **metadata columns** (kept in the Qdrant payload for filtering).

### `/ingest` (live SSE)
- Stage tracker shows: **Read → Build docs → Chunk → Embed → Index**.
- Each stage renders a card on the right:
  - **Chunk** — histogram, total chunks, avg/min/max chars, sample chunks with
    overlap highlighted in the steel-blue accent.
  - **Embed** — progress bar, dense vector preview (first 8 dims), sparse top-5
    tokens by weight.
  - **Index** — Qdrant collection info + point count.

### `/chunks`
- Paginated viewer (50/page) over the entire collection.
- Search box (substring) + filters (`priority`, `module`, `jira_id`).
- Each chunk card: ids, payload badges, tags, full text.
- Chunks used in the most recent chat answer are **outlined in the steel-blue accent**.

### `/chat`
- Chat on the right; the query pipeline stage tracker on the left updates per query.
- After each turn the assistant shows a collapsible **Pipeline trace**:
  - The query rewrites
  - Dense top-N vs sparse top-N vs RRF-fused top-N
  - Re-rank before/after table (moved rows highlighted)
  - The exact context chunks sent to the LLM
  - Final answer with `[Chunk N]` citations
- Two modes auto-detected:
  - **Answer** — grounded Q&A on the test cases.
  - **Generate** — e.g. *"create a new test case for VWO checkout coupon codes"*
    drafts a structured test case (Title / Preconditions / Steps / Expected /
    Priority / Tags) using retrieved similar test cases as templates.

---

## The test-case corpus

`testcase/VWO_2000_Test_Cases.csv` — 2,000 rows across 24 VWO product modules
(Login, A/B Testing, Visual Editor, Heatmaps, Session Recordings, Billing,
API/Webhooks, …). Jira-import friendly: every row carries a `jira_id`
(`VWO-####`) plus `title`, `preconditions`, `steps`, `expected`, `priority`,
`tags`, `module`. Regenerate or resize it with:

```bash
python testcase/generate_testcases.py --rows 2000
```

---

## Tunables (`.env` / top of `rag/config.py`)

| Knob               | Default | Meaning                                          |
|--------------------|---------|--------------------------------------------------|
| `CHUNK_SIZE`       | 1000    | Max chars per chunk before splitting             |
| `CHUNK_OVERLAP`    | 150     | Chars repeated between adjacent chunks           |
| `TOP_N_HYBRID`     | 20      | Candidates per dense / sparse search             |
| `TOP_K_RERANK`     | 4       | Final chunks sent to the LLM after rerank        |
| `RRF_K`            | 60      | Reciprocal Rank Fusion smoothing constant        |
| `REWRITE_ENABLED`  | 1       | Use Groq to generate alt phrasings before search |
| `RAG_LITE`         | (auto)  | Force the dependency-free local backend          |

---

## Concept explainer

Open [`RAG_Explorer_Explained.html`](RAG_Explorer_Explained.html) in any browser
(or host it) for an animated, diagram-driven walkthrough of how this advanced
RAG was built — the "vibe coding" story from CSV to grounded answer.

---

## Troubleshooting

- **Connection refused on 6333** — only relevant if you set `QDRANT_URL` to a
  server. Default is embedded; nothing to start.
- **Groq 401** — `.env` is missing or `GROQ_API_KEY` is wrong. The app still
  runs and shows retrieved chunks as a fallback.
- **First query is slow (real mode)** — bge-m3 + reranker downloading + warming.
  Subsequent calls are sub-second. Use `RAG_LITE=1` to skip downloads entirely.
- **Out-of-memory on bge-m3** — keep `BGE_USE_FP16=1` and reduce `INGEST_BATCH=16`.
- **Port 5050 busy** — change `PORT` in `.env`.
```
