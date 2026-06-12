# task_plan.md

Created by GitHub Copilot on 2026-06-12

Phase 0 - Initialization
- Create project memory files: `task_plan.md`, `findings.md`, `progress.md`, `LLM.md` (done)
- Halt execution until discovery questions are answered

Phase 1 - Discovery (completed)
- North Star: Produce a Formal Test Plan Markdown file per JIRA issue (no individual test cases).
- Integrations: Atlassian JIRA (read-only) and optional GROQ/OpenGPT (GROQ is optional and gated by `useGroq`).
- Source of Truth: JIRA issue fields (`summary`, `description`, `acceptance criteria`, labels, custom fields).
- Delivery Payload: Local Markdown file saved under `chapter_03_BLAST_FW/` and returned to client.
- Behavioral Rules: Reuse VWO template; do not edit JIRA; keep credentials in `.env` by default.

Phase 2 - Link
- Implement `server/jira.js` to verify read-only connection to JIRA using `.env` (done).
- Add `/api/generate` and `/api/save` endpoints (done).

Phase 3 - Architect
- Implement deterministic generator `buildTestPlanMarkdown` for stable outputs (done).

Next steps: User validation and iterative refinements; optionally enable auto-commit or CI triggers for saved artifacts.
