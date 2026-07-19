# 05 — Company Docs (PDF / MD)

**Drop here:** company PDFs and Markdown — process docs, onboarding guides,
QA checklists, style guides. Formats: `*.pdf`, `*.md`, `*.txt`, `*.docx`

## Ingestion contract (doc_chunker.py)
- Header-first recursive split, **500–800 tokens**, **15% overlap**
- Requirement IDs (regex `REQ-\d+`, `FR-\d+`) extracted into
  `metadata.requirement_ids`
- Metadata: `title`, `file_path`, `section_heading`, `requirement_ids`,
  `source_type="doc"`
