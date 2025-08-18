#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-http://127.0.0.1:8000}
USER=${BB_USER:-tester}
PASS=${BB_PASS:-secret}
FILENAME=${BB_FILE:-probe.txt}
CONTENT=${BB_CONTENT:-"Hallo von Backbrain 5.2 – Smoke Test."}

echo "[1] Auth token holen..." >&2
RAW=$(curl -s -X POST "$BASE/api/v1/auth/token" -H "Content-Type: application/x-www-form-urlencoded" -d "username=$USER&password=$PASS" || true)
TOKEN=$(python3 - <<'PY' "$RAW"
import json,sys
try:
    print(json.loads(sys.argv[1])['access_token'])
except Exception:
    pass
PY
)
if [ -z "${TOKEN}" ]; then
  echo "FEHLER: Kein Token erhalten" >&2
  echo "$RAW" >&2
  exit 1
fi
echo "Token OK (${TOKEN:0:14}…)" >&2

echo "[2] Datei schreiben ($FILENAME)..." >&2
WRITE=$(curl -s -X POST "$BASE/api/v1/files/write-file" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"kind":"entries","name":"'$FILENAME'","content":"'$CONTENT'"}')
echo "$WRITE" | jq '.' 2>/dev/null || echo "$WRITE"

echo "[3] Datei lesen..." >&2
READ=$(curl -s -G "$BASE/api/v1/files/read-file" -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "kind=entries" --data-urlencode "name=$FILENAME")
echo "$READ" | jq '.' 2>/dev/null || echo "$READ"

echo "[4] Zusammenfassung erzeugen..." >&2
SUMM=$(curl -s -X POST "$BASE/api/v1/summarizer/summarize-file" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"kind":"entries","name":"'$FILENAME'","style":"bullet"}')
echo "$SUMM" | jq '.' 2>/dev/null || echo "$SUMM"

echo "[5] Summary-Liste..." >&2
LIST=$(curl -s -G "$BASE/api/v1/files/list" -H "Authorization: Bearer $TOKEN" --data-urlencode "base=SUMMARY")
echo "$LIST" | jq '.' 2>/dev/null || echo "$LIST"

echo "FERTIG" >&2#!/usr/bin/env bash
set -euo pipefail

# Backbrain Smoke Test
# 1) /health & /ready
# 2) Obtain JWT token
# 3) Write test entry file
# 4) Summarize file
# 5) Prefilter enforcement
# 6) Prefixed list-files success

BASE=${BASE:-http://127.0.0.1:8000}
USER_NAME=${USER_NAME:-tester}
USER_PASSWORD=${USER_PASSWORD:-secret}
FILE_NAME=${FILE_NAME:-smoke_$(date +%Y%m%d_%H%M%S).txt}
PREFIX_FOR_LIST=${PREFIX_FOR_LIST:-smoke_}
CONTENT=${CONTENT:-"Dies ist ein Smoke-Test Eintrag #smoke 2025-08-17 Betrag 13,40."}

log() { printf "[%s] %s\n" "$(date -Iseconds)" "$*"; }
fail() { log "FAIL: $*"; exit 1; }

curl_json() { curl -sS "$@" -H 'Accept: application/json'; }

log "1) Health check";
curl -fsS "$BASE/health" >/dev/null || fail "Health endpoint down";
log "   OK";

log "2) Ready check";
curl -fsS "$BASE/ready" >/dev/null || fail "Ready endpoint down";
log "   OK";

log "3) Obtain token";
RAW=$(curl -sS -X POST "$BASE/api/v1/auth/token" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=${USER_NAME}&password=${USER_PASSWORD}" || true)
TOKEN=$(python3 - <<'PY' "$RAW"
import json,sys
try: print(json.loads(sys.argv[1])['access_token'])
except Exception: pass
PY
)
[ -n "$TOKEN" ] || fail "Token retrieval failed: $RAW";
log "   Token OK";

AUTH_HEADER=( -H "Authorization: Bearer $TOKEN" )

log "4) Write test file: $FILE_NAME";
WRITE_RESP=$(curl_json -X POST "$BASE/api/v1/files/write-file" "${AUTH_HEADER[@]}" -H 'Content-Type: application/json' \
  -d "{\"kind\":\"entries\",\"name\":\"$FILE_NAME\",\"content\":\"$CONTENT\"}") || fail "write-file request failed";
echo "$WRITE_RESP" | grep -q '"status":"ok"' || fail "write-file unexpected response: $WRITE_RESP";
log "   Write OK";

log "5) Summarize file";
SUMM_RESP=$(curl_json -X POST "$BASE/api/v1/summarizer/summarize-file" "${AUTH_HEADER[@]}" -H 'Content-Type: application/json' \
  -d "{\"kind\":\"entries\",\"name\":\"$FILE_NAME\",\"style\":\"short\"}") || fail "summarize-file request failed";
echo "$SUMM_RESP" | grep -q '"summary_path"' || fail "No summary_path in response: $SUMM_RESP";
MODEL=$(python3 - <<'PY'
import json,sys
try:
    print(json.load(sys.stdin)['model'])
except Exception: pass
PY
<<<"$SUMM_RESP")
log "   Summarize model=$MODEL";

log "6) Prefilter enforcement (should fail)";
set +e
PF_RESP=$(curl -s -o /dev/stderr -w 'HTTP_CODE:%{http_code}' "$BASE/api/v1/files/list-files?kind=entries&limit=500" "${AUTH_HEADER[@]}")
PF_CODE=$(echo "$PF_RESP" | sed -n 's/.*HTTP_CODE://p')
set -e
if [ "$PF_CODE" = 400 ]; then
  log "   Prefilter rule enforced (400)"
else
  log "   WARNING: Expected 400 got $PF_CODE"
fi

log "7) Prefixed list-files (should succeed)";
LF_RESP=$(curl_json "$BASE/api/v1/files/list-files?kind=entries&prefix=$PREFIX_FOR_LIST&limit=50" "${AUTH_HEADER[@]}") || fail "list-files with prefix failed";
echo "$LF_RESP" | grep -q '"items"' || fail "list-files missing items";
log "   List-files OK";

log "DONE: Smoke test completed.";
