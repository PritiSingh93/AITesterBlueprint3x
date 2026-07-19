# 01 — Selenium Framework Repo

**Drop here:** git clone of [ATB13xSeleniumAdvanceFramework](https://github.com/PramodDutta/ATB13xSeleniumAdvanceFramework)

```bash
git clone https://github.com/PramodDutta/ATB13xSeleniumAdvanceFramework .
```

## Ingestion contract (code_chunker.py)
- Files: `*.java`, `testng*.xml`, `*.properties`, `pom.xml`, `README*`
- AST-aware split (tree-sitter) by function/class, **300–500 tokens**
- No overlap, except forced splits on oversized functions
- Metadata: `repo_name`, `file_path`, `class_name`, `method_name`,
  `last_commit_hash`, `source_type="selenium_code"`
- Phase 2: hourly `git pull` → diff-only re-ingest of changed files
