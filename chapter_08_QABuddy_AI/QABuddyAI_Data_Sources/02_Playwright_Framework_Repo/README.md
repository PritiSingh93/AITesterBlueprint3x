# 02 — Playwright Framework Repo

**Drop here:** git clone of [Advance-Playwright-Framework](https://github.com/PramodDutta/Advance-Playwright-Framework)

```bash
git clone https://github.com/PramodDutta/Advance-Playwright-Framework .
```

## Ingestion contract (code_chunker.py)
- Files: `*.ts`, `*.js`, `playwright.config.*`, `package.json`, `README*`
- AST-aware split (tree-sitter) by function/class/`describe`/`test` block,
  **300–500 tokens**
- No overlap, except forced splits on oversized functions
- Metadata: `repo_name`, `file_path`, `class_name`, `method_name`,
  `last_commit_hash`, `source_type="playwright_code"`
- Phase 2: hourly `git pull` → diff-only re-ingest of changed files
