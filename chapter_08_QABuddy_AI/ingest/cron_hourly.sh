#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# QABuddyAI — Phase 2 hourly auto-ingestion.  BUILT BUT NOT ENABLED.
#
# Enable on the droplet (only after the go-signal) with:
#   crontab -e
#   0 * * * * cd /opt/qabuddy && docker compose exec -T backend bash ingest/cron_hourly.sh >> /var/log/qabuddy_ingest.log 2>&1
#
# What one run does:
#   1. git pull both framework repos (delta re-ingest happens via the
#      content-hash manifest — only changed files are re-embedded)
#   2. JIRA delta sync via MCP (updated >= last successful sync)
#   3. Hash-diff scan over all other folders (new/changed/deleted files)
# ---------------------------------------------------------------------------
set -uo pipefail
cd "$(dirname "$0")/.."

echo "=== QABuddyAI hourly ingest: $(date -u +%FT%TZ) ==="

for repo in \
  "QABuddyAI_Data_Sources/01_Selenium_Framework_Repo" \
  "QABuddyAI_Data_Sources/02_Playwright_Framework_Repo"; do
  if [ -d "$repo/.git" ]; then
    git -C "$repo" pull --ff-only || echo "WARN: git pull failed for $repo"
  fi
done

python ingest/jira_sync.py --delta || echo "WARN: jira sync failed"

# Delta by default: unchanged files are skipped via the manifest.
python ingest/run_full_ingest.py --source all

echo "=== done: $(date -u +%FT%TZ) ==="
