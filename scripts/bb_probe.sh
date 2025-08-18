#!/usr/bin/env bash
set -euo pipefail

# ===== Config =====
: "${BB_API_BASE:?Set BB_API_BASE, e.g., https://backbrain5.fly.dev}"
BB_NAME="${BB_NAME:-2025-08-18__gpt_probe.md}"
BB_KIND="${BB_KIND:-entries}"
BB_CONTENT="${BB_CONTENT:-Hello from bb_probe.sh}"
ENABLE_PUSHGATEWAY="${ENABLE_PUSHGATEWAY:-false}"
PUSHGATEWAY_URL="${PUSHGATEWAY_URL:-}"
PG_JOB="${PG_JOB:-bb_probe}"
PG_INSTANCE="${PG_INSTANCE:-local}"
ENABLE_STEP_SUMMARY="${ENABLE_STEP_SUMMARY:-false}"

auth_args=()
[[ -n "${BB_API_KEY:-}" ]] && auth_args=(-H "X-API-Key: ${BB_API_KEY}")

if [[ -n "${BB_API_KEY:-}" ]]; then
  auth_args=(-H "X-API-Key: ${BB_API_KEY}")
fi
say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
fail() { echo "::error ::$*"; exit 1; }
jqc() { if command -v jq >/dev/null 2>&1; then jq -c . || cat; else cat; fi; }

# Globals, die call() setzt
LAST_HTTP_CODE=""
LAST_URL=""
LAST_BODY_FILE=""
LAST_HDR_FILE=""

# call METHOD URL [JSON_DATA]
call() {
  local method="$1"; shift
  local url="$1"; shift
  local data="${1:-}"
  local tmpb tmph code
  tmpb=$(mktemp)
  tmph=$(mktemp)
  if [[ -n "$data" ]]; then
    if [[ ${#auth_args[@]-0} -gt 0 ]]; then
      code=$(curl -s -o "$tmpb" -D "$tmph" -w "%{http_code}" -X "$method" "$url" -H "Content-Type: application/json" "${auth_args[@]}" -d "$data")
    else
      code=$(curl -s -o "$tmpb" -D "$tmph" -w "%{http_code}" -X "$method" "$url" -H "Content-Type: application/json" -d "$data")
    fi
  else
    if [[ ${#auth_args[@]-0} -gt 0 ]]; then
      code=$(curl -s -o "$tmpb" -D "$tmph" -w "%{http_code}" -X "$method" "$url" "${auth_args[@]}")
    else
      code=$(curl -s -o "$tmpb" -D "$tmph" -w "%{http_code}" -X "$method" "$url")
    fi
  fi
  LAST_HTTP_CODE="$code"
  LAST_URL="$url"
  LAST_BODY_FILE="$tmpb"
  LAST_HDR_FILE="$tmph"
}

show_last() {
  echo "HTTP ${LAST_HTTP_CODE}  ${LAST_URL}"
  jqc <"$LAST_BODY_FILE" || true
  echo
}

get_header() {
  local name="$1"
  awk -v k="^$name:" 'BEGIN{IGNORECASE=1} $0 ~ k {print $2}' "$LAST_HDR_FILE" | tr -d '\r'
}

push_metric() {
  [[ "$ENABLE_PUSHGATEWAY" != "true" ]] && return 0
  [[ -z "$PUSHGATEWAY_URL" ]] && return 0
  local metric="$1" value="$2"
  local payload="# TYPE ${metric} gauge
${metric}{job=\"${PG_JOB}\",instance=\"${PG_INSTANCE}\"} ${value}
"
  curl -fsS --retry 2 --data-binary "$payload" "${PUSHGATEWAY_URL}/metrics/job/${PG_JOB}/instance/${PG_INSTANCE}" >/dev/null || true
}

append_summary() {
  [[ "$ENABLE_STEP_SUMMARY" != "true" ]] && return 0
  [[ -z "${GITHUB_STEP_SUMMARY:-}" ]] && return 0
  printf "%s\n" "$1" >> "$GITHUB_STEP_SUMMARY"
}

# ===== Probe sequence =====
summary_md="### Backbrain5.2 Smoke Probe\n\n"
summary_md+="- Base: \`$BB_API_BASE\`\n"

say "Health"
call GET "${BB_API_BASE}/health"
show_last
[[ "$LAST_HTTP_CODE" == "200" ]] || fail "Health failed ($LAST_HTTP_CODE)"
push_metric "bb_probe_health_ok" 1
summary_md+="- Health: **OK** (200)\n"

say "Write"
call POST "${BB_API_BASE}/write-file" "{\"kind\":\"${BB_KIND}\",\"name\":\"${BB_NAME}\",\"content\":\"${BB_CONTENT}\"}"
show_last
if [[ "$LAST_HTTP_CODE" != "200" && "$LAST_HTTP_CODE" != "409" ]]; then
  fail "Write failed ($LAST_HTTP_CODE)"
fi
push_metric "bb_probe_write_ok" 1
summary_md+="- Write: **OK** (${LAST_HTTP_CODE})\n"

say "Read (capture ETag)"
call GET "${BB_API_BASE}/read-file?name=${BB_NAME}&kind=${BB_KIND}"
show_last
[[ "$LAST_HTTP_CODE" == "200" ]] || fail "Read failed ($LAST_HTTP_CODE)"
ETAG="$(get_header etag || true)"
push_metric "bb_probe_read_ok" 1
summary_md+="- Read: **OK** (200), ETag: \`${ETAG:-none}\`\n"

if [[ -n "${ETAG:-}" ]]; then
  say "Read (If-None-Match ETag)"
  local_tmpb=$(mktemp); local_tmph=$(mktemp)
    if [[ ${#auth_args[@]-0} -gt 0 ]]; then
      ncode=$(curl -s -o "$local_tmpb" -D "$local_tmph" -w "%{http_code}" -H "If-None-Match: ${ETAG}" "${BB_API_BASE}/read-file?name=${BB_NAME}&kind=${BB_KIND}" "${auth_args[@]}")
    else
      ncode=$(curl -s -o "$local_tmpb" -D "$local_tmph" -w "%{http_code}" -H "If-None-Match: ${ETAG}" "${BB_API_BASE}/read-file?name=${BB_NAME}&kind=${BB_KIND}")
    fi
  echo "HTTP ${ncode}  ${BB_API_BASE}/read-file?name=${BB_NAME}&kind=${BB_KIND} (If-None-Match)"
  [[ "$ncode" == "304" ]] || fail "ETag check failed ($ncode)"
  push_metric "bb_probe_read_not_modified" 1
  summary_md+="- ETag 304: **OK**\n"
fi

say "List"
call GET "${BB_API_BASE}/list-files?kind=${BB_KIND}"
show_last
[[ "$LAST_HTTP_CODE" == "200" ]] || fail "List failed ($LAST_HTTP_CODE)"
if ! grep -q "\"${BB_NAME}\"" "$LAST_BODY_FILE"; then
  echo "::warning ::list-files did not include ${BB_NAME} (possible path mismatch: check inbox_dir vs write target)"
fi
push_metric "bb_probe_list_ok" 1
summary_md+="- List: **OK** (200)\n"

say "Summaries"
call GET "${BB_API_BASE}/get_all_summaries"
show_last
[[ "$LAST_HTTP_CODE" == "200" ]] || fail "Summaries failed ($LAST_HTTP_CODE)"
push_metric "bb_probe_summaries_ok" 1
summary_md+="- Summaries: **OK** (200)\n"

say "Metrics (optional)"
mcode=$(curl -s -o /dev/null -w "%{http_code}" "${BB_API_BASE}/metrics" || true)
echo "HTTP ${mcode}  ${BB_API_BASE}/metrics"
if [[ "$mcode" == "200" ]]; then
  push_metric "bb_probe_metrics_ok" 1
  summary_md+="- Metrics: **OK** (200)\n"
else
  summary_md+="- Metrics: n/a (${mcode})\n"
fi

append_summary "$summary_md"
echo -e "\nAll checks passed."
