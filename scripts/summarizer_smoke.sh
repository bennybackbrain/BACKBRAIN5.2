#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE_URL:-http://127.0.0.1:8000}"
USER="${BB_USER:-admin}"
PASS="${BB_PASS:-changeme}"
TMPFILE="/tmp/bb_sum_test_$$.txt"

echo "[summarizer_smoke] creating sample file" > "$TMPFILE"

# Auth (assumes default admin exists)
TOKEN=$(curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"username":"'"$USER"'","password":"'"$PASS"'"}' \
  "$BASE/api/v1/auth/token" | jq -r '.access_token')

if [[ -z "$TOKEN" || "$TOKEN" == null ]]; then
  echo "Auth failed" >&2; exit 1
fi

NAME="smoke_$(date +%s).txt"
CONTENT="Backbrain Summarizer Smoke Test $(date -Iseconds)"

curl -s -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"kind":"entries","name":"'"$NAME"'","content":"'"$CONTENT"'"}' \
  "$BASE/api/v1/files/write-file" > /dev/null

RESP=$(curl -s -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"kind":"entries","name":"'"$NAME"'"}' \
  "$BASE/api/v1/summarizer/summarize-file")

MODEL=$(echo "$RESP" | jq -r '.model')
SUMMARY_PATH=$(echo "$RESP" | jq -r '.summary_path')

if [[ -z "$SUMMARY_PATH" || "$SUMMARY_PATH" == null ]]; then
  echo "Summarizer failed: $RESP" >&2; exit 1
fi

echo "Model: $MODEL"
echo "Summary path: $SUMMARY_PATH"
echo "OK"
