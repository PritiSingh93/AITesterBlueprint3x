# RAG Explorer

A hands-on RAG (Retrieval-Augmented Generation) demo app. It ingests PDF/text
documents, chunks them, embeds the chunks with **Nomic Embed** (via the Nomic
Atlas API), stores them in a local **ChromaDB** vector store, retrieves the
top matching chunks for a question, and generates an answer with **Groq**
(`openai/gpt-oss-120b`). A second tab, **Embedding Explorer**, visualizes how
embeddings actually work.

## Stack

- **Backend:** Python + FastAPI, layered PDF extraction (`pypdf` →
  `pdfplumber` → OCR fallback), ChromaDB (embedded, persisted to disk — no
  separate server process), `nomic` SDK for embeddings, `groq` SDK for
  generation.
- **Frontend:** React (Vite) + Tailwind CSS, `recharts` for the embedding
  scatter plot, `lucide-react` for icons.

## 1. Get API keys

- **Groq** (LLM): https://console.groq.com/keys
- **Nomic** (embeddings): https://atlas.nomic.ai — free API key

## 2. Backend setup

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

copy .env.example .env    # Windows
# cp .env.example .env     # macOS/Linux
# then edit .env and paste in GROQ_API_KEY and NOMIC_API_KEY

python run.py
```



The API runs at `http://localhost:8000`. Interactive docs at
`http://localhost:8000/docs`.

### Optional: OCR fallback for PDFs with no text layer

Ingestion tries three PDF extraction methods in order — `pypdf`, then
`pdfplumber`, then OCR — falling through only when the previous method
returns no usable text. The OCR step is needed for PDFs exported from design
tools (Figma, Canva, etc.) that render "text" as vector outlines or flattened
images rather than real embedded glyphs — the included VWO PRD PDF is one of
these. The `pytesseract`/`pdf2image` **pip packages** are already in
`requirements.txt`, but OCR also needs two **system binaries** that pip can't
install:

**Windows:**

```powershell
winget install --id UB-Mannheim.TesseractOCR
winget install --id oschwartz10612.Poppler
```

Then, if they aren't automatically on `PATH`, set the paths in `backend/.env`:

```
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
POPPLER_PATH=C:\path\to\poppler\Library\bin
```

**macOS:** `brew install tesseract poppler`
**Linux (Debian/Ubuntu):** `sudo apt-get install tesseract-ocr poppler-utils`

On macOS/Linux, `TESSERACT_CMD`/`POPPLER_PATH` can usually stay blank (both
binaries land on `PATH` automatically). Without these installed, ingestion
still works fine for any PDF/`.txt`/`.md` file that has a real text layer —
OCR is only invoked as a last resort.

## 3. Frontend setup

In a second terminal:

```bash
cd frontend
npm install
copy .env.example .env    # Windows (optional — defaults to localhost:8000)
npm run dev
```

Open `http://localhost:5173`.

## 4. Using the app

**RAG Flow tab**

1. Click **Run Ingestion Pipeline** — reads every `.pdf` / `.txt` / `.md`
   file in `data/` (the included VWO PRD PDF is there already), splits each
   into ~500-1000 token chunks, embeds them with Nomic, and stores them in
   ChromaDB. Chunk previews appear on the left, with an **OCR** badge on any
   chunk whose source PDF needed the OCR fallback.
2. Optionally use **Upload PDF / Text** to add another document to `data/`
   before re-running ingestion.
3. Ask a question on the right. The app embeds your question, retrieves the
   top 4 most similar chunks from ChromaDB, sends them + your question to
   Groq, and shows both the retrieved chunks (with similarity scores) and the
   generated answer.

**Embedding Explorer tab**

- **Text → Vector:** embed any word/sentence and see the raw vector values.
- **Similarity Comparison:** compare two words (e.g. "King" vs "Queen") and
  see their cosine similarity.
- **Word Embedding Map:** a 2D PCA projection of a preset word list, showing
  related concepts (king/queen, man/woman, car/truck) clustering together.

## Project layout

```
chapter_07_RAG/Basic_RAG/
  data/                    # source documents (PDF/txt/md) ingested by the pipeline
  backend/
    app/
      config.py            # env-driven settings
      chunking.py          # paragraph/sentence-aware chunker
      ingestion.py          # PDF/text loading -> chunk records
      embeddings.py         # Nomic Atlas API wrapper
      vectorstore.py        # ChromaDB persistent client
      llm.py                # Groq answer generation
      routes/
        ingest.py           # /api/ingest, /api/upload, /api/status
        query.py            # /api/query
        explorer.py         # /api/embeddings/*
      main.py               # FastAPI app
    run.py
    requirements.txt
    .env.example
  frontend/
    src/
      components/           # DocumentPanel, QueryPanel, EmbeddingExplorerTab, ...
      api.js                 # fetch wrapper for the backend
      App.jsx
    package.json
    .env.example
```

## Notes

- Chunk sizing uses a ~4-characters-per-token heuristic (no tokenizer
  download required) to stay in the 500-1000 token range while breaking on
  paragraph/sentence boundaries. See `backend/app/chunking.py`.
- PDF text extraction falls through `pypdf` → `pdfplumber` → OCR
  (`pytesseract` + `pdf2image`), only advancing to the next method when the
  previous one returns no usable text. See `backend/app/ingestion.py` and
  the "Optional: OCR fallback" section above for the required system
  binaries.
- ChromaDB data persists under `backend/chroma_db/` (git-ignored). Re-running
  ingestion clears and rebuilds the collection from whatever is currently in
  `data/`.
- Groq model defaults to `openai/gpt-oss-120b` (Groq's hosted "GPT-OSS 120B"
  model); override with `GROQ_MODEL` in `backend/.env` if needed.
