# SOP — Formal Test Plan Template (Layer 1)

Native QA template (NOT the external `test-plan-create-skill`). The generator must fill these 13 sections.

| # | Section | Content |
|---|---------|---------|
| 1 | Objective | What this testing effort proves, tied to the issue. |
| 2 | Scope | In Scope / Out of Scope bullet lists. |
| 3 | Inclusions | Specific features/flows/areas covered. |
| 4 | Test Environments | OS / browser / device / env (e.g. staging) targets. |
| 5 | Defect Reporting | Where + how defects are logged (Jira project, severity scale). |
| 6 | Test Strategy | Test types: functional, regression, API, UI, edge, negative. |
| 7 | Schedule | Phase / Owner / Dates table (`TBD` where unknown). |
| 8 | Deliverables | Artifacts produced (test cases, report, defect log). |
| 9 | Entry Criteria | Preconditions to start testing. |
| 10 | Exit Criteria | Conditions to stop / sign off. |
| 11 | Tools | Test + automation + reporting tooling. |
| 12 | Risks & Mitigations | Risk / Mitigation table. |
| 13 | Approvals | Role / Name sign-off table. |

## Rules
- Derive everything from the Jira issue. Unknown specifics → `TBD`, never invented.
- Professional, concise, formal QA tone.
- Output is JSON (see `gemini.md` §3d) → rendered deterministically to Markdown.