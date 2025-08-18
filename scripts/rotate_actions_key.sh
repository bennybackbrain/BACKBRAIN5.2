#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-https://backbrain5.fly.dev}"
TOKEN="${TOKEN:?JWT bearer token required (export TOKEN)}"
NAME="gpt-actions-$(date +%Y%m%d-%H%M%S)"

echo "Creating new API key name=$NAME"
RESP=$(curl -fsS -X POST "$BASE/api/v1/keys?name=$NAME" -H "Authorization: Bearer $TOKEN")
echo "$RESP" | jq .
RAW=$(echo "$RESP" | jq -r '.api_key // empty')
if [[ -z "$RAW" ]]; then
  echo "No api_key field returned" >&2
  exit 1
fi
FILE=".new_actions_api_key"
echo "$RAW" > "$FILE"
chmod 600 "$FILE"
echo "New key stored in $FILE (remember to update GPT Action X-API-Key)"

echo "List existing keys:"
curl -fsS -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/keys" | jq '.[] | {id,name,created_at}'
