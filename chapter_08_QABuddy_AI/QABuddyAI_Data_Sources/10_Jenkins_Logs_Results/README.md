# 10 — Jenkins Logs & Results

**Drop here:** build console logs and test-result files.
Formats: `*.log` / `*.txt` (console), `*.xml` (JUnit/TestNG), `*.json` (Allure)
**Naming convention:** `<job>_<build#>_console.log`, `<job>_<build#>_results.xml`

## Ingestion contract (jenkins_chunker.py)
- **One build run = one chunk**, **300–500 tokens**, no overlap
- Failed steps / stack traces isolated as **separate high-priority chunks**
  (test name + error message + top stack-trace lines) — powers flaky-test
  analysis and failure RCA
- Metadata: `job_name`, `build_number`, `build_status`, `failed_step`,
  `timestamp`, `source_type="jenkins"`
- Phase 2: hourly poll of Jenkins API for builds newer than last seen
