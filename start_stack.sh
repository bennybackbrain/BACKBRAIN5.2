#!/usr/bin/env bash
set -Eeuo pipefail

echo "[stack] Starte Backbrain API + n8n (lokal)"

if ! command -v docker >/dev/null 2>&1; then
  echo "[stack] Docker nicht gefunden" >&2
  exit 1
fi
if ! command -v docker compose >/dev/null 2>&1; then
  echo "[stack] 'docker compose' CLI nicht gefunden (Docker Desktop aktualisieren)" >&2
  exit 1
fi

echo "[stack] Erstelle Datenordner n8n_data falls fehlend"
mkdir -p n8n_data

echo "[stack] Starte Dienste (api + n8n)"
docker compose -f docker-compose.yml -f docker-compose.stack.yml up -d --build

echo "[stack] Warte auf API (Port 8000)"
for i in {1..30}; do
  if curl -sf http://127.0.0.1:8000/health >/dev/null; then
    echo "[stack] API bereit"
    break
  fi
  sleep 1
  if [[ $i -eq 30 ]]; then
    echo "[stack] API nicht erreichbar" >&2
  fi
done

echo "[stack] n8n UI: http://localhost:5678"
echo "[stack] Importiere das Workflow JSON manuell über die n8n UI (oder per Clipboard)."
echo "[stack] Webhook Test (nach Aktivierung / Klick auf Execute):"
cat <<'EOF'
curl -X POST http://localhost:5678/webhook-test/summarize-file \
  -H 'Content-Type: application/json' \
  -d '{"file_path":"01_inbox/beispiel.txt"}'
EOF

echo "[stack] Zum Stoppen: docker compose -f docker-compose.yml -f docker-compose.stack.yml down"
