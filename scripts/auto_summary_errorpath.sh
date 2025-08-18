#!/usr/bin/env bash
# Test Auto-Summary Error Path with local-fallback storage (WebDAV disabled)
# This simulates WebDAV outage by optionally toggling WEBDAV_DISABLED secret.
# Usage:
#   BB_API_BASE=https://backbrain5.fly.dev ./scripts/auto_summary_errorpath.sh
# Optional toggle (requires flyctl + FLY_API_TOKEN):
#   FLY_API_TOKEN=... ./scripts/auto_summary_errorpath.sh --toggle-webdav
# Env overrides:
#   POLL_MAX=20 POLL_SLEEP=2 QUIET=1 BB_API_KEY=... (if public write requires key)
set -euo pipefail

BB_API_BASE="${BB_API_BASE:-https://backbrain5.fly.dev}"
BB_API_KEY="${BB_API_KEY:-}"
NAME="errorpath_$(date +%s).txt"
TOGGLE="${1:-}"
POLL_MAX=${POLL_MAX:-20}
POLL_SLEEP=${POLL_SLEEP:-2}
QUIET=${QUIET:-0}

_hdr=(-H "Content-Type: application/json")
if [[ -n "$BB_API_KEY" ]]; then _hdr+=( -H "X-API-Key: $BB_API_KEY" ); fi

log(){ [[ "$QUIET" == "1" ]] || echo "$*"; }
need_fly(){ command -v fly >/dev/null 2>&1 || { echo "::error ::flyctl fehlt"; exit 2; }; [[ -n "${FLY_API_TOKEN:-}" ]] || { echo "::error ::FLY_API_TOKEN fehlt"; exit 2; }; }

toggle_on(){ need_fly; log "==> Set WEBDAV_DISABLED=1 (simulate outage)"; fly secrets set WEBDAV_DISABLED="1" -a backbrain5 >/dev/null; fly deploy -a backbrain5 >/dev/null; }

toggle_off(){ need_fly; log "==> Unset WEBDAV_DISABLED"; fly secrets unset WEBDAV_DISABLED -a backbrain5 >/dev/null || true; fly deploy -a backbrain5 >/dev/null; }

cleanup(){ if [[ "$TOGGLE" == "--toggle-webdav" ]]; then toggle_off; fi }
trap cleanup EXIT

if [[ "$TOGGLE" == "--toggle-webdav" ]]; then toggle_on; fi

log "==> Write-file triggers auto-summary (expect storage=local-fallback)"
resp=$(curl -sS -X POST "$BB_API_BASE/write-file" "${_hdr[@]}" -d "{\"kind\":\"entries\",\"name\":\"$NAME\",\"content\":\"error path smoke\"}") || { echo "::error ::write-file failed"; exit 1; }
status=$(echo "$resp" | jq -r '.status // empty')
if [[ -z "$status" ]]; then echo "::error ::invalid write-file response"; echo "$resp"; exit 1; fi
log "   status=$status name=$NAME"

log "==> Poll summaries for ${NAME}.summary.md (max ${POLL_MAX}*${POLL_SLEEP}s)"
found=""; last_payload=""
for i in $(seq 1 "$POLL_MAX"); do
  list=$(curl -sS "$BB_API_BASE/get_all_summaries" || echo '{}')
  last_payload="$list"
  echo "$list" | jq -r '.summaries[].name // empty' | grep -q "${NAME}.summary.md" && { found="yes"; break; }
  sleep "$POLL_SLEEP"
done
if [[ -z "$found" ]]; then
  echo "::error ::Summary not found within timeout"; echo "$last_payload" | jq '.summaries | map(.name)' || true
  if command -v fly >/dev/null 2>&1; then log "==> Recent logs"; fly logs -a backbrain5 --no-tail -n 150 || true; fi
  exit 1
fi
log "✅ Summary created"

log "==> Check metrics for local-fallback + ok"
metrics=$(curl -sS "$BB_API_BASE/metrics" || true)
if echo "$metrics" | grep -q 'bb_auto_summary_total{[^}]*status="ok"[^}]*storage="local-fallback"'; then
  log "✅ Counter shows ok/local-fallback"
else
  echo "⚠️  Counter missing ok/local-fallback (maybe WebDAV still enabled?)"
fi

# Optionally show histogram line
if echo "$metrics" | grep -q '^bb_auto_summary_duration_seconds_bucket'; then
  log "==> Histogram present"
fi

exit 0
