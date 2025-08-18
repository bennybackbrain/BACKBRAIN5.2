#!/usr/bin/env bash
set -euo pipefail
: "${PUBLIC_URL:?PUBLIC_URL required}"; : "${GPT_API_KEY:?GPT_API_KEY required}";
BASE="$PUBLIC_URL"
log(){ printf '[%s] %s\n' "$(date -Iseconds)" "$*"; }
log "List files"
curl -s -G "$BASE/api/v1/files/list-files" -H "X-API-Key: $GPT_API_KEY" --data-urlencode kind=entries | jq .
log "Write file"
curl -s -X POST "$BASE/api/v1/files/write-file" -H "X-API-Key: $GPT_API_KEY" -H 'Content-Type: application/json' -d '{"kind":"entries","name":"hello.txt","content":"It works 🚀"}' | jq .
log "Summarize"
curl -s -X POST "$BASE/api/v1/summarizer/summarize-file" -H "X-API-Key: $GPT_API_KEY" -H 'Content-Type: application/json' -d '{"kind":"entries","name":"hello.txt","style":"bullet"}' | jq .
log "Summarize prefix (hello)"
curl -s -X POST "$BASE/api/v1/summarizer/summarize-prefix" -H "X-API-Key: $GPT_API_KEY" -H 'Content-Type: application/json' -d '{"kind":"entries","prefix":"hello","limit":10,"style":"short"}' | jq .
log DONE
