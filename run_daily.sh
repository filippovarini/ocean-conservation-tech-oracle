#!/usr/bin/env bash
# Daily ingestion run for the ocean-tech catalog. Invoked by cron.
# Must cd into the project dir first: llm.py's load_dotenv() reads .env from cwd,
# and ingest/UI share ./catalog.db on this box's disk.
set -euo pipefail

cd /home/fvarini/marine-technology-inventory

mkdir -p logs
exec >> logs/ingest.log 2>&1

echo "===== $(date -Is) ingest run start ====="
.venv/bin/python ingest.py run --days 7
echo "===== $(date -Is) ingest run done ====="
