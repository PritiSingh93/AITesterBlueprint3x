# 09 — PRD / SRS / BRD / FRD

**Drop here:** all requirement documents (PDF preferred; MD/DOCX accepted).
**Naming convention:** `PRD_<feature>.pdf`, `SRS_<system>.pdf`, … — the prefix
is parsed into `doc_kind` so you can filter "only PRDs".

## Ingestion contract (doc_chunker.py — same as folder 05)
- Header-first recursive split, **500–800 tokens**, **15% overlap**
- Requirement IDs (regex `REQ-\d+`, `FR-\d+`) preserved in text AND extracted
  into `metadata.requirement_ids` — this powers RTM building and
  missing-test-case detection
- Metadata: `doc_kind=prd|srs|brd|frd`, `title`, `section_heading`,
  `requirement_ids`, `source_type="prd"`
