# MASTER PROMPT — Build "QABuddyAI": a LIVE Hybrid RAG System for QA Engineers

## 1. ROLE
You are a senior AI/ML architect. Design and implement an end-to-end,
self-hosted, multi-source Hybrid RAG system called **QABuddyAI** for the QA
team of my company.

## 2. OBJECTIVE
A chatbot where a QA engineer asks one question and gets a **cited answer**
grounded in our Selenium framework, Playwright framework, VWO test-case
repository (5,000 TCs), PRDs, and JIRA bug history.

## 3. USE CASES (must support)
- Onboarding help for new QA engineers
- Central QA knowledge base ("KB brain") that understands our code repos
- Test-failure analysis, RCA, bug triage
- Test-case discovery: find existing TCs, find test plans, review coverage,
  identify MISSING test cases
- Build RTM (Requirements Traceability Matrix)
- Flaky-test history: feed and retrieve flaky patterns
- Framework-level coding help: scripts, conventions, best practices
- Available 24x7, always updated, token-efficient

Target: Copilot + this RAG + JIRA ID → 70–80% test coverage
(vs 30–40% with Copilot + JIRA alone).

## 4. DATA SOURCES (10 — create one ingestion folder per source)
1. Selenium repo — github.com/PramodDutta/ATB13xSeleniumAdvanceFramework
2. Playwright repo — github.com/PramodDutta/Advance-Playwright-Framework
3. Test cases — 5,000 TCs in CSV/XLSX (testdata.csv)
4. JIRA tickets — pulled via JIRA MCP connection using a JQL I will provide
5. Company PDFs and MD files
6. Figma designs: ER diagrams, user guides, wireframes (PHASE 2 only)
7. Meeting notes / recording transcripts (text)
8. Lucidchart diagrams exported to text
9. PRD / SRS / BRD / FRD (all PDFs)
10. Jenkins logs and results

## 5. TECH CONSTRAINTS
- Embedding model: open-source only — recommend one and justify
  (dense + sparse hybrid capability preferred)
- Vector DB: open-source, self-hosted, must support hybrid search
  (dense + keyword/sparse) and metadata filtering — recommend and justify
- Reranker: recommend an open-source cross-encoder
- Deployment: Docker Compose on a DigitalOcean droplet (VPN/private access,
  company-internal use)
- Answer LLM: recommend API vs self-hosted with trade-offs

## 6. CHUNKING REQUIREMENTS
Propose structure-aware chunking PER SOURCE TYPE, with exact chunk size and
overlap for each, and justify:
- Code repos: split by function/method, never mid-function
- Test cases: 1 row = 1 chunk
- JIRA: 1 ticket = 1 chunk
- PDFs/PRDs: heading/section-aware
- Jenkins logs: per failure block, noise stripped
Define a metadata schema (source, file_path/url, jira_key, status, component,
version, content_hash) that enables citations and filtered retrieval.

## 7. RETRIEVAL PIPELINE
Hybrid retrieval (dense + sparse) → RRF fusion → cross-encoder rerank →
top-k context → answer LLM with a system prompt that:
- answers ONLY from retrieved context
- cites every claim as [source: file_path or jira_key]
- says "not found" and names the likely missing source folder when context
  is insufficient

## 8. PHASING
- Phase 1: 10 folders scaffolded, manual/batch ingestion, JIRA via MCP+JQL,
  chatbot API + simple UI, evaluation harness (golden set of ~30–50 real QA
  questions; measure hit-rate@k, citation correctness, faithfulness)
- Phase 2: HOURLY auto-ingestion — detect new/changed test cases, code
  commits, JIRA updates (updated >= -1h JQL) via content-hash diffing;
  idempotent upserts and deletions
- Phase 3: Figma ingestion, optional self-hosted LLM, Slack bot, auto-RTM

## 9. DELIVERABLES
1. Architecture diagram and justification of all model/DB choices
2. Folder scaffold for the 10 sources
3. Ingestion pipeline (loaders → chunkers → embedder → vector DB upsert)
4. Retrieval + chat API with citations
5. Docker Compose deployment for DigitalOcean
6. Evaluation harness and tuning recommendations

## 10. INPUTS I WILL PROVIDE
- JIRA MCP connection + JQL
- Access to both GitHub repos
- Sample files for each folder