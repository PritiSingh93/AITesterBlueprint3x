# RAG Test Case Generator

A RAG (Retrieval-Augmented Generation) app that turns a PRD/requirements
document into QA test cases. It ingests PDF/text documents, chunks them,
embeds the chunks with **Mistral Embed**, stores them in a local
**ChromaDB** vector store, retrieves the top matching chunks for a request,
and generates structured test cases with **Groq** (`llama-3.1-8b-instant`).

This is a web app port of the `AI3X_RAG_TestCases_generation.json` Langflow
flow in this folder: File → Split Text → Mistral Embeddings → Chroma
(ingestion), and Chat Input → Mistral Embeddings → Chroma → Parser → Prompt
Template → Groq → Chat Output (retrieval + generation).

## Stack

- **Backend:** Python + FastAPI, layered PDF extraction (`pypdf` →
  `pdfplumber`), ChromaDB (embedded, persisted to disk — no separate server
  process), `mistralai` SDK for embeddings, `groq` SDK for generation.
- **Frontend:** React (Vite) + Tailwind CSS, `react-markdown` for rendering
  generated test cases, `lucide-react` for icons.

## 1. Get API keys

- **Groq** (LLM): https://console.groq.com/keys
- **Mistral AI** (embeddings): https://console.mistral.ai/api-keys

## 2. Backend setup

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

copy .env.example .env    # Windows
# cp .env.example .env     # macOS/Linux
# then edit .env and paste in GROQ_API_KEY and MISTRAL_API_KEY

python run.py
```

The API runs at `http://localhost:8000`. Interactive docs at
`http://localhost:8000/docs`.

## 3. Frontend setup

In a second terminal:

```bash
cd frontend
npm install
copy .env.example .env    # Windows (optional — defaults to localhost:8000)
npm run dev
```

Open `http://localhost:5174`.

## 4. Hosted / live deployment notes

A public frontend is deployed on Vercel and a public FastAPI backend is
exposed on Render:

- Frontend: `https://ragpipeline1000testcasegenerator-9px2pj294.vercel.app`
- Backend: `https://rag-testcase-backend.onrender.com`

In the frontend, the API target is configured through
`frontend/.env` / `frontend/.env.example` using
`VITE_API_BASE_URL=https://rag-testcase-backend.onrender.com`.

For the deployed backend to work, the following environment variables must be
set in the Render service dashboard:

- `GROQ_API_KEY`
- `MISTRAL_API_KEY`
- `PYTHON_VERSION=3.12.4`

After any backend redeploy or restart, the vector store is rebuilt from the
current contents of the backend container filesystem. If the deployed service
is restarted, re-run **Upload PRD / Text** and **Run Ingestion Pipeline**
again before generating test cases.

## 5. Using the app

1. Click **Upload PRD / Text** to add a requirements document (PDF, `.txt`,
   or `.md`) to `data/`.
2. Click **Run Ingestion Pipeline** — splits the document into ~1000
   character chunks (200 char overlap, matching the Langflow SplitText
   node), embeds them with Mistral, and stores them in ChromaDB.
3. Describe what to generate test cases for (or pick a suggestion). The app
   embeds your request, retrieves the top 10 most similar chunks from
   ChromaDB, sends them + your request to Groq, and returns structured test
   cases (Title / Preconditions / Steps / Expected Result) alongside the
   retrieved chunks that informed them.

## Project layout

```
chapter_07_RAG/RAG_TestCase_generator/
  AI3X_RAG_TestCases_generation.json   # source Langflow flow this app ports
  data/                    # requirements documents (PDF/txt/md) ingested by the pipeline
  backend/
    app/
      config.py            # env-driven settings
      chunking.py          # paragraph/sentence-aware chunker
      ingestion.py          # PDF/text loading -> chunk records
      embeddings.py         # Mistral AI embeddings wrapper
      vectorstore.py        # ChromaDB persistent client
      llm.py                # Groq test-case generation
      routes/
        ingest.py           # /api/ingest, /api/upload, /api/status
        query.py            # /api/query
      main.py               # FastAPI app
    run.py
    requirements.txt
    .env.example
  frontend/
    src/
      components/           # DocumentPanel, TestCasePanel, PipelineFlow, TopNav
      api.js                 # fetch wrapper for the backend
      App.jsx
    package.json
    .env.example
```

## Notes

- Chroma collection name (`langflow_ai3x_TC`) and chunk size/overlap
  (1000/200 chars) match the source Langflow flow's SplitText and Chroma
  node settings.
- No OCR fallback — this flow doesn't use one. If a PDF has no extractable
  text layer, it's skipped during ingestion rather than failing the whole
  batch (see `backend/app/ingestion.py`).
- ChromaDB data persists under `backend/chroma_db/` (git-ignored) for local
  runs. Re-running ingestion clears and rebuilds the collection from whatever
  is currently in `data/`.
- For the Render-deployed backend, uploaded data and Chroma state are
  container-local. After a redeploy or server reset, re-upload and re-run
  ingestion before generating test cases again.
- Groq model defaults to `llama-3.1-8b-instant` (matching the Langflow
  flow); override with `GROQ_MODEL` in `backend/.env` if needed.
