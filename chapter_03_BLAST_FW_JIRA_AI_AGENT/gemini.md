# gemini.md

JSON I/O schema and flow for Test Plan Generator (Data-First rule)

## Input (from JIRA - read-only)
{
  "jira_id": "string (e.g. KAN-4)",
  "jiraBaseUrl": "optional string (overrides .env)",
  "jiraEmail": "optional string (overrides .env)",
  "jiraToken": "optional string (overrides .env)",
  "useGroq": "optional boolean - if true the GROQ/OpenGPT API will be used",
  "groqApiUrl": "optional string",
  "groqApiKey": "optional string"
}

Notes: The generator reads a single JIRA issue identified by `jira_id`. By default it will use server-side `.env` values when optional fields are omitted. It must not modify or write back to JIRA.

## Output (local Markdown Test Plan)
{
  "file_path": "chapter_03_BLAST_FW/<JIRA_ID>_Test_Plan.md",
  "content": "string (markdown)"
}

## Behavioral rules
- Reuse VWO template structure when present.
- Do not include individual test cases; produce a Formal Test Plan (Objective, Scope, Strategy, Entry/Exit Criteria, Risks, Assumptions, Dependencies, Traceability, Sign-off).
- Store credentials in server-side `.env` for convenience; client may supply overrides per request.

## Example flow
1. Client POST `/api/generate` with `jira_id` (and optional overrides).
2. Server fetches JIRA issue (read-only) using `server/jira.js` (env defaults apply).
3. If `useGroq` is true and GROQ keys present, server calls GROQ/OpenGPT to refine output.
4. Otherwise server builds the Test Plan using the deterministic template (`buildTestPlanMarkdown`).
5. Client may POST `/api/save` with `jira_id` and `markdown` to persist the file under `chapter_03_BLAST_FW/`.

## Notes
- Keep `gemini.md` updated when schema or output shape changes.
