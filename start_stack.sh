#!/usr/bin/env bash
set -Eeuo pipefail

echo "[stack] Starte Backbrain API (ohne n8n)"

if ! command -v docker >/dev/null 2>&1; then
  echo "[stack] Docker nicht gefunden" >&2
  exit 1
fi
if ! command -v docker compose >/dev/null 2>&1; then
  echo "[stack] 'docker compose' CLI nicht gefunden (Docker Desktop aktualisieren)" >&2
  exit 1
fi

echo "[stack] Starte API Dienst"
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

echo "[stack] Zum Stoppen: docker compose -f docker-compose.yml -f docker-compose.stack.yml down"
