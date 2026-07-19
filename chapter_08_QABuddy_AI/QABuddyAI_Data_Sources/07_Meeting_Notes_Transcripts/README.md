# 07 — Meeting Notes & Recording Transcripts

**Drop here:** meeting notes and recording transcripts as text.
Formats: `*.txt`, `*.md`, `*.vtt` / `*.srt` (converted to plain text on ingest)
**Naming convention:** `YYYY-MM-DD_topic.md` — date is parsed into metadata.

## Ingestion contract (meeting_chunker.py)
- Split by topic / speaker turn, **300–500 tokens**, **10% overlap**
- Metadata: `meeting_date`, `title`, `source_type="meeting"`
