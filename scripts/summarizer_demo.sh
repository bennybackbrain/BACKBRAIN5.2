#!/usr/bin/env bash
set -euo pipefail
: "${TOKEN:?TOKEN required}";
BASE=${BASE:-http://127.0.0.1:8000}
log(){ printf '[%s] %s\n' "$(date -Iseconds)" "$*"; }
NAME=${1:-hello.txt}
log "Write"
curl -s -X POST "$BASE/api/v1/files/write-file" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"kind":"entries","name":"'$NAME'","content":"It works 🚀"}' | jq .
log "Summarize short"
curl -s -X POST "$BASE/api/v1/summarizer/summarize-file" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"kind":"entries","name":"'$NAME'","style":"short"}' | jq .
log "Summarize bullet"
curl -s -X POST "$BASE/api/v1/summarizer/summarize-file" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"kind":"entries","name":"'$NAME'","style":"bullet"}' | jq .
log "Summarize prefix"
curl -s -X POST "$BASE/api/v1/summarizer/summarize-prefix" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"kind":"entries","prefix":"'${NAME%%.*}'","limit":5,"style":"short"}' | jq .
log DONE
