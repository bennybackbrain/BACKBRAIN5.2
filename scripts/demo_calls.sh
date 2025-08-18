#!/usr/bin/env bash
set -euo pipefail
# Quick probe:
# 1 mkdir 01_inbox
# 2 write demo.txt
# 3 read demo.txt
# Only prints on non-2xx.
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
USERNAME="${USERNAME:-tester}"
PASSWORD="${PASSWORD:-secret}"
TOKEN="${TOKEN:-}"
obtain_token() {
  if [[ -n "$TOKEN" ]]; then TOKEN=${TOKEN//$'\n'/}; return 0; fi
  local resp
  resp=$(curl -s -X POST "$BASE_URL/api/v1/auth/token" -H 'Content-Type: application/x-www-form-urlencoded' -d "username=${USERNAME}&password=${PASSWORD}" || true)
  if command -v jq >/dev/null 2>&1; then
    TOKEN=$(printf '%s' "$resp" | jq -r '.access_token // empty')
  else
    TOKEN=$(python3 - <<'PY' "$resp"
import json,sys
try: print(json.loads(sys.argv[1]).get('access_token',''))
except: pass
PY
)
  fi
  TOKEN=${TOKEN//$'\n'/}
  if [[ -z "$TOKEN" ]]; then echo "auth STATUS=000"; echo "$resp"; exit 1; fi
}
call_or_report() {
  local label="$1"; shift
  local bodyfile="$1"; shift
  local code
  code=$("$@" -o "$bodyfile" -w '%{http_code}' || true)
  if [[ ! $code =~ ^2 ]]; then echo "${label} STATUS=$code"; cat "$bodyfile"; fi
}
main() {
  obtain_token
  call_or_report mkdir /tmp/mkdir.json curl -s -X POST "$BASE_URL/api/v1/webdav/mkdir" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"path":"01_inbox"}'
  call_or_report write-file /tmp/write.json curl -s -X POST "$BASE_URL/api/v1/files/write-file" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"kind":"entries","name":"demo.txt","content":"Hallo Backbrain 👋"}'
  call_or_report read-file /tmp/read.json curl -s -G "$BASE_URL/api/v1/files/read-file" -H "Authorization: Bearer $TOKEN" --data-urlencode 'kind=entries' --data-urlencode 'name=demo.txt'
}
main "$@"
