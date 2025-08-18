#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8000}"
API_KEY="${API_KEY:?set X-API-Key}"
# Health
curl -fsS "$BASE/health" >/dev/null
# Drei Entries schreiben (triggert Summaries)
for i in 1 2 3; do
  curl -fsS -X POST "$BASE/api/v1/files/write-file" \
   -H "Content-Type: application/json" \
   -H "X-API-Key: ${API_KEY}" \
   -d "{\"kind\":\"entries\",\"name\":\"2025-08-18__query-smoke-${i}--abcd00${i}.md\",\"content\":\"Wetter 2025 und Bank 2024: Notiz ${i}.\"}" >/dev/null
done
sleep 2
# Query
curl -fsS -X POST "$BASE/api/v1/query" \
 -H "X-API-Key: ${API_KEY}" \
 -H "Content-Type: application/json" \
 -d '{"query":"Was verbindet Wetter 2025 und Bankauszug 2024?","top_k":10}' | jq .
