# 04 — JIRA Tickets

**Drop here:** raw JSON snapshots, one file per issue (`<KEY>.json`).
Primary sync path: **JIRA MCP connection + JQL** (JQL lives in `config/jql.txt`) —
`ingest/jira_sync.py` writes the snapshots here, then ingests the delta only.
Do not call the JIRA REST API directly — always go through the MCP connection.

## Ingestion contract (jira_chunker.py)
- **One ticket = one chunk** (summary + description + comments)
- Split by comment thread past ~**800 tokens**; ticket ID repeated in every sub-chunk
- Metadata: `jira_id`, `project`, `status`, `priority`, `issue_type`, `sprint`,
  `labels`, `assignee`, `updated_date`, `source_type="jira"`
- Phase 2: hourly sync of issues `updated >= -1h` (state file tracks last sync)
