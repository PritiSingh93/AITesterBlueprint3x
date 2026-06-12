# findings.md

Created by GitHub Copilot on 2026-06-12

Research notes and discoveries recorded during prototype development.

- 2026-06-12: Standardized on canonical JIRA ID example `KAN-4` across the project. Adopt flexible `jira_id` input.
- 2026-06-12: GROQ/OpenGPT available but for deterministic output we implemented a local generator `buildTestPlanMarkdown`.
- 2026-06-12: Server module `server/jira.js` reads `.env` by default and accepts overrides from the client.
- 2026-06-12: Save endpoint `/api/save` writes markdown to the workspace folder `chapter_03_BLAST_FW/`.

- 2026-06-12: Added `mockFields` support to `/api/generate` to allow local verification without contacting JIRA. This is useful for testing the generator and save flow when JIRA credentials are not available.

Open items:
- Confirm whether to enable auto-commit of saved files to git.