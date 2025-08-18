#!/usr/bin/env bash
# Auto-Summary E2E Smoke Test
# Usage:
#   BB_API_BASE=https://backbrain5.fly.dev ./scripts/auto_summary_smoke.sh
# Optional:
#   BB_API_KEY=... (if public write disabled)
# Exits 0 on success, 1 on failure.
set -euo pipefail

BB_API_BASE="${BB_API_BASE:-https://backbrain5.fly.dev}"
BB_API_KEY="${BB_API_KEY:-}"
NAME="autosum_smoke_$(date +%s).txt"
CONTENT="Auto-summary E2E smoke at $(date -u +%FT%TZ)"
POLL_MAX=${POLL_MAX:-20}         # loops (default 20 * 2s = 40s)
POLL_SLEEP=${POLL_SLEEP:-2}
QUIET=${QUIET:-0}

_hdr=(-H "Content-Type: application/json")
if [[ -n "$BB_API_KEY" ]]; then _hdr+=( -H "X-API-Key: $BB_API_KEY" ); fi

log(){ [[ "$QUIET" == "1" ]] || echo "$*"; }

log "==> Write-file: $NAME"
resp="$(curl -sS -X POST "$BB_API_BASE/write-file" "${_hdr[@]}" \
  -d "{\"kind\":\"entries\",\"name\":\"$NAME\",\"content\":\"$CONTENT\"}")"
status="$(echo "$resp" | jq -r '.status // empty')"
if [[ -z "$status" ]]; then
  echo "::error ::Write-file response invalid"; echo "$resp"; exit 1
fi
log "   status=$status"

log "==> Poll summaries for ${NAME}.summary.md"
found=""; last_payload=""
for i in $(seq 1 "$POLL_MAX"); do
  list="$(curl -sS "$BB_API_BASE/get_all_summaries")" || list='{}'
  last_payload="$list"
  echo "$list" | jq -r '.summaries[].name // empty' | grep -q "${NAME}.summary.md" && { found="yes"; break; }
  sleep "$POLL_SLEEP"
done

if [[ -z "$found" ]]; then
  echo "::error ::Summary not found within timeout (${POLL_MAX}*${POLL_SLEEP}s)"
  echo "$last_payload" | jq '.summaries | map(.name)' || true
  if command -v fly >/dev/null 2>&1; then
    log "==> Recent logs (200 lines)"
    fly logs -a backbrain5 --no-tail -n 200 || true
  fi
  exit 1
fi

log "✅ Summary created: ${NAME}.summary.md"
echo "$last_payload" | jq -r --arg f "${NAME}.summary.md" \
  '.summaries[] | select(.name==$f) | {name, content}'

# Optional ETag read check
log "==> Read-file + ETag check"
r1="$(curl -si "$BB_API_BASE/read-file?name=$NAME&kind=entries")"
etag="$(printf "%s" "$r1" | awk -F': ' 'tolower($1)=="etag"{print $2}' | tr -d '\r')"
if [[ -n "$etag" ]]; then
  code="$(curl -s -o /dev/null -w '%{http_code}' -H "If-None-Match: $etag" "$BB_API_BASE/read-file?name=$NAME&kind=entries")"
  if [[ "$code" == "304" ]]; then
    log "   304 OK (ETag)"
  else
    log "   ETag conditional GET unexpected code: $code"
  fi
else
  log "   No ETag header captured"
fi

exit 0
