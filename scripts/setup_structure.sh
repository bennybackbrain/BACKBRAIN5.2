#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8000}"
: "${TOKEN:?TOKEN env var (Bearer) required}"

mkdir_call(){
  local p="$1";
  curl -s -X POST "$BASE/api/v1/webdav/mkdir" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "{\"path\":\"$p\"}" | jq -r '.status? // .error?.code? // "ok"'
}

echo "Creating base folders (idempotent)..." >&2
for d in BACKBRAIN5.2 BACKBRAIN5.2/01_inbox BACKBRAIN5.2/summaries BACKBRAIN5.2/archive BACKBRAIN5.2/_tmp; do
  printf '%-30s -> %s\n' "$d" "$(mkdir_call "$d")"
done

echo "Done." >&2
