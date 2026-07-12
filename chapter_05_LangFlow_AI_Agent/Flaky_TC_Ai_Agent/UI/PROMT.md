# Prompts — Flaky Test Analyzer AI Agent

The prompts behind this project, captured so you can reproduce or remix it. Two layers:

1. **The agent prompt** — the instruction sent *into* the LangFlow flow at run time.
2. **The build prompt** — the prompt used to generate the React UI that sits in front of the agent.

> Note: the build prompt below is the canonical, cleaned version of what produced the UI in
> `ui/`. Copy it, swap your own flow ID / component IDs, and an AI coding agent will regenerate
> the same front-end.

---

## 1. The Agent Prompt (run-time input to the flow)

This is the text the UI sends as `input_value` on every analysis. Short on purpose — the heavy
lifting lives in the agent's own system instructions inside LangFlow.

```
Analyze these two Playwright runs and tell me which build has the most failing/flaky test.
```

The two `results.json` files are not pasted into the prompt — they are uploaded and injected as
`tweaks` on the flow's two **File** components (`File-daKW7`, `File-IKmcY`). The agent is told to
return three sections: `FLAKY_TESTS`, `CONSISTENT_FAILURES`, and `RERUN_RECOMMENDATION`.

---

## 2. The Build Prompt (used to create the UI)

Paste this into your AI coding agent (Claude Code, Cursor, etc.) from inside an empty `ui/` folder.

```
Build a lightweight React + Vite front-end for a LangFlow AI agent called the
"Flaky Test Analyzer". The UI lets me pick TWO Playwright results.json files
(Build A vs Build B), runs them through the LangFlow flow, and renders the agent's
flaky / consistent-failure / rerun report as clean markdown.

STACK
- React 18 + Vite. Plain CSS (no UI framework). Module type.
- react-markdown + remark-gfm to render the agent's markdown report (tables, lists).
- No backend of my own — the browser talks straight to LangFlow.

CORS / PROXY (important — do this exactly)
- LangFlow's file-upload endpoint does NOT answer the browser's CORS preflight
  (OPTIONS returns 422), so a direct cross-origin upload fails with "Failed to fetch".
- Fix it with a Vite dev proxy: forward same-origin "/api" requests to the LangFlow
  server (default http://localhost:7861, overridable via a LANGFLOW_URL env var).
  All app requests use a relative /api path so they stay same-origin.

API FLOW (two calls per analysis)
1. Upload each file:  POST /api/v1/files/upload/{flowId}  (multipart, header x-api-key)
   -> returns a server-side file_path.
2. Run the flow:      POST /api/v1/run/{flowId}?stream=false
   body: {
     output_type: "chat",
     input_type: "text",
     input_value: <the prompt>,
     session_id: <stable id>,
     tweaks: {
       "File-daKW7": { path: [pathA] },
       "File-IKmcY": { path: [pathB] }
     }
   }
3. Pull the assistant text out of
   outputs[0].outputs[0].results.message.text
   (with sensible fallbacks), plus token usage from message.properties.usage.

DEFAULT CONFIG (prefilled, editable)
- flowId: a468f029-e319-4ed4-bbc9-27836ac4cdc1
- File component IDs: File-daKW7 (Build A), File-IKmcY (Build B)
- x-api-key: BLANK by default — never hard-code a key. Read it from a Connection
  panel (persisted to localStorage) or from VITE_API_KEY in a gitignored .env.
- default prompt: "Analyze these two Playwright runs and tell me which build has
  the most failing/flaky test."

UI
- Two drag-and-drop upload cards (Build A / Build B). On drop, parse the
  results.json locally and show a quick stat preview per file:
  passed / failed / flaky / skipped / duration.
- A "Run Analysis" button (disabled until both files are present).
- A Report panel: rendered markdown + model name + token usage, with Copy and
  Download buttons.
- A collapsible "Connection" settings panel (base URL, x-api-key, flow ID, the two
  File component IDs) that saves to localStorage.
- Clear loading and error states (surface the LangFlow error detail, not just
  "Failed to fetch").

FILE LAYOUT
- src/App.jsx            layout + run pipeline orchestration
- src/lib/api.js         upload + run + response parsing (export an analyze() pipeline)
- src/lib/playwright.js  parse results.json into the per-file stat preview
- src/components/UploadCard.jsx   drag/drop card with the stat preview
- src/components/Report.jsx       markdown report + token usage + copy/download
- src/components/Settings.jsx     editable connection settings
- vite.config.js         the /api -> LangFlow proxy
- README.md              how it works + how to run

CONSTRAINTS
- Do not commit any API key. Keep the key blank in defaults and .env in .gitignore.
- Keep it dependency-light: react, react-dom, react-markdown, remark-gfm only.
```

---

## How to adapt it for your own flow

| Change | Where |
|--------|-------|
| Different flow | swap `flowId` in `src/lib/api.js` (`DEFAULTS`) |
| Different File component names | read them from `GET /api/v1/flows/{flowId}`, update `fileIdA` / `fileIdB` |
| LangFlow on another host/port | set `LANGFLOW_URL` (proxy) and/or the Connection panel base URL |
| More than two inputs | add upload cards + more `tweaks` keys in `runFlow()` |

See `ui/README.md` for the UI internals and `../README.md` for the chapter overview.