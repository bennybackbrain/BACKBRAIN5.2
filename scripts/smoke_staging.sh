#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-https://backbrain5-staging.fly.dev}"

echo "[Staging Smoke] BASE=$BASE"

echo "Health:"; curl -fsS "$BASE/health" | jq .

echo "Write:"; curl -fsS -X POST "$BASE/write-file" \
  -H 'Content-Type: application/json' \
  -d '{"name":"smoke.txt","kind":"entries","content":"Hello Staging"}' | jq .

sleep 1

echo "Read:"; curl -fsS "$BASE/read-file?name=smoke.txt&kind=entries" | jq .

echo "List:"; curl -fsS "$BASE/list-files?kind=entries" | jq '.files[:5]'

echo "Metrics sample:"; curl -fsS "$BASE/metrics" | grep -m1 http_requests_total || true

echo "Done."
