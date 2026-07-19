# QABuddyAI — Project Build Prompt

Paste this into Claude Code / GHCP / Cursor (or any coding agent) to scaffold the actual
project. It encodes every decision from the architecture plan so the agent doesn't have to
guess. Fill in the `[ ]` placeholders before running it.

---

```
Build QABuddyAI: a Hybrid RAG chatbot for QA engineers, deployed as a Docker Compose stack
on a single DigitalOcean droplet. Follow this spec exactly — do not substitute components
without asking me first.

GOAL
A chat API + minimal frontend that answers QA questions grounded in 10 source types, with
inline citations, using hybrid (dense+sparse) retrieval and reranking.

TECH STACK (fixed — do not change)
- Embedding: BGE-M3, served via Hugging Face Text-Embeddings-Inference (TEI), Docker, CPU.
- Vector DB: Qdrant, self-hosted via Docker, single collection named "qabuddy", using named
  vectors for dense + sparse so hybrid queries run through Qdrant's Universal Query API.
- Reranker: bge-reranker-v2-m3, served via TEI's reranker mode (or a small FastAPI wrapper
  if TEI doesn't support it directly).
- Generation LLM: Groq API, model llama-3.3-70b-versatile (swap model name if I say so),
  called via the Groq Python SDK. API key from environment variable GROQ_API_KEY.
- Backend: Python, FastAPI.
- Orchestration/chunking: plain Python (no LangChain/LlamaIndex dependency required unless
  it clearly saves time — keep the ingestion pipeline simple and debuggable).
- Frontend: minimal chat UI — Streamlit is fine for phase 1, don't over-build this.
- Deployment: single docker-compose.yml with services: qdrant, tei-embed, tei-rerank,
  backend, frontend, nginx.

FOLDER STRUCTURE (already created locally — read the README.md in each before writing its
ingester)
QABuddyAI_Data_Sources/
  01_Selenium_Framework_Repo/       <- git clone of [github.com/PramodDutta/ATB13xSeleniumAdvanceFramework]
  02_Playwright_Framework_Repo/     <- git clone of [github.com/PramodDutta/Advance-Playwright-Framework]
  03_TestCases_CSV_XLSX/            <- testdata.csv, ~5000 rows
  04_JIRA_Tickets/                  <- JSON snapshots, primary sync via JIRA MCP + JQL
  05_Company_Docs_PDF_MD/
  06_Figma_Design_Phase2/           <- inactive in phase 1, skip
  07_Meeting_Notes_Transcripts/
  08_LucidChart_Exports/
  09_PRD_SRS_BRD_FRD/
  10_Jenkins_Logs_Results/

BUILD IN THIS ORDER

1. `ingest/chunkers/` — one chunker module per source type, each returning
   (text, metadata_dict) tuples. Follow these rules exactly:
   - code_chunker.py: AST-aware split (use tree-sitter) by function/class, 300-500 tokens,
     no overlap except forced splits on oversized functions. Metadata: repo_name, file_path,
     class_name, method_name, last_commit_hash, source_type.
   - testcase_chunker.py: one CSV/XLSX row per chunk, 150-300 tokens, no overlap. Metadata:
     tc_id, module, priority, automation_status, linked_jira_id, source_type="test_case".
   - jira_chunker.py: one ticket per chunk (summary+description+comments), split by comment
     thread past ~800 tokens, ticket ID repeated in every sub-chunk. Metadata: jira_id,
     project, status, priority, issue_type, sprint, labels, assignee, updated_date.
   - doc_chunker.py (for company docs + PRD/SRS/BRD/FRD): header-first recursive split,
     500-800 tokens, 15% overlap. Extract and preserve requirement IDs (regex for patterns
     like REQ-\d+, FR-\d+) into metadata.requirement_ids.
   - meeting_chunker.py: split by topic/speaker-turn, 300-500 tokens, 10% overlap.
   - lucidchart_chunker.py: one diagram/sub-flow per chunk, 300-600 tokens, no overlap.
   - jenkins_chunker.py: one build run per chunk, isolate failed steps/stack traces as
     separate high-priority chunks, 300-500 tokens, no overlap. Metadata: job_name,
     build_number, build_status, failed_step, timestamp.

2. `ingest/embed_and_upsert.py` — calls TEI for dense+sparse vectors, upserts into Qdrant
   with the metadata from step 1. Must be idempotent (upsert by deterministic point ID
   derived from source+path+chunk_index, so re-running doesn't duplicate).

3. `ingest/run_full_ingest.py` — walks all 10 folders + both repos, calls the right chunker
   per source_type, calls embed_and_upsert. This is the phase-1 manual entrypoint
   (`python run_full_ingest.py --source all` or `--source selenium` etc.).

4. `ingest/jira_sync.py` — connects to the JIRA MCP server, runs a JQL I provide via
   config/jql.txt, saves raw JSON to 04_JIRA_Tickets/, then calls jira_chunker +
   embed_and_upsert on the delta only (updated since last successful sync, tracked in a
   local state file).

5. `backend/retrieval.py` — given a query: embed it (dense+sparse via TEI), run Qdrant
   hybrid query (with optional metadata filters e.g. source_type, repo), take top ~20,
   rerank with bge-reranker-v2-m3, return top ~6-8 chunks with metadata.

6. `backend/generate.py` — builds the prompt using the runtime prompt in
   QABuddyAI_Generation_Prompt.md (read that file, use it verbatim as the base template),
   fills {context} and {question}, calls Groq, returns the answer + citations used.

7. `backend/main.py` — FastAPI app, single POST /ask endpoint (question in, answer+citations
   out), plus GET /health.

8. `frontend/app.py` — Streamlit chat UI calling the /ask endpoint. Show citations as
   clickable/expandable references under each answer.

9. `docker-compose.yml` + `nginx/` — wire all services together, nginx as reverse proxy with
   Let's Encrypt via certbot. Environment variables via .env (never commit secrets):
   GROQ_API_KEY, JIRA_API_TOKEN, JIRA_BASE_URL, QDRANT_API_KEY.

10. `ingest/cron_hourly.sh` + a crontab entry (phase 2, build but don't enable yet unless I
    say go): runs git pull on both repos (diff-only re-ingest of changed files), jira_sync.py,
    and a folder hash-diff scan on the other 8 folders.

DO NOT
- Do not swap Qdrant for another vector DB, or BGE-M3 for another embedding model, without
  asking me — these were chosen deliberately for hybrid search support.
- Do not build authentication/multi-tenant support in phase 1 — single internal tool is fine.
- Do not call the JIRA API directly — always go through the JIRA MCP connection.
- Do not fabricate sample data for the two GitHub repos or the 5000 test cases — wait for me
  to populate the folders, and build against the folder/README contract instead.

DELIVERABLE
A working docker-compose stack I can run with `docker compose up` on a fresh DigitalOcean
droplet, plus a README explaining how to run phase-1 ingestion the first time.

Ask me before starting if anything above is ambiguous — don't guess on JQL, repo access, or
Groq model choice.
```

---

## How to use this
1. Fill in the two GitHub repo URLs and your company name at the top.
2. Paste the whole block into your coding agent as the first message in a fresh session.
3. Point it at the `QABuddyAI_Data_Sources/` folder structure and `QABuddyAI_Generation_Prompt.md`
   (both already created) so it reads the contracts instead of inventing its own.
   `QABuddyAI_System_Prompt.md` is the high-level MASTER build prompt for context.