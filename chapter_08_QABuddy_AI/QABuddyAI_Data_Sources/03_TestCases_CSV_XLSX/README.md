# 03 — Test Cases (CSV / XLSX, ~5000 TC)

**Drop here:** `testdata.csv` and any other `*.csv` / `*.xlsx` test-case exports.

**Expected columns (mapped in config, extra columns become payload):**
`tc_id, title, steps, expected, module, priority, automation_status, linked_jira_id`

## Ingestion contract (testcase_chunker.py)
- **One row = one chunk**, **150–300 tokens**, no overlap — never split a TC
- Embedded text = title + steps + expected; the rest is filterable metadata
- Metadata: `tc_id`, `module`, `priority`, `automation_status`,
  `linked_jira_id`, `source_type="test_case"`
