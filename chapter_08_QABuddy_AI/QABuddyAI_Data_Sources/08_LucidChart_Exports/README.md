# 08 — Lucidchart Exports (as text)

**Drop here:** Lucidchart flows exported as text — architecture flows,
test-flow diagrams, process swimlanes.
Formats: `*.md`, `*.txt` (recommended: Mermaid blocks or numbered step lists;
a PNG alongside is fine but only the text is embedded).

## Ingestion contract (lucidchart_chunker.py)
- **One diagram / sub-flow = one chunk**, **300–600 tokens**, no overlap
- Metadata: `diagram_name`, `source_type="diagram"`
