#!/usr/bin/env bash
# Development helper to start Backbrain5.2 FastAPI with auto-reload.
# Usage:
#   ./run_dev.sh              # default host 127.0.0.1:8000, reload on
#   HOST=0.0.0.0 PORT=9000 ./run_dev.sh
#   RELOAD=0 ./run_dev.sh     # disable auto-reload

set -Eeuo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${PROJECT_ROOT}/.venv"
REQ_FILE="${PROJECT_ROOT}/requirements.txt"

log(){ printf "[run_dev] %s\n" "$*"; }

# 1. Ensure virtual environment exists
if [[ ! -d "$VENV" ]]; then
  log "Creating virtual environment (.venv)"
  python3 -m venv "$VENV"
fi

# 2. Activate venv
# shellcheck source=/dev/null
source "$VENV/bin/activate"

# 3. Install/refresh dependencies if needed (hash requirements)
if [[ -f "$REQ_FILE" ]]; then
  REQ_HASH_FILE="${VENV}/.requirements.sha1"
  NEW_HASH="$(shasum "$REQ_FILE" | awk '{print $1}')"
  OLD_HASH="$(cat "$REQ_HASH_FILE" 2>/dev/null || true)"
  if [[ "$NEW_HASH" != "$OLD_HASH" ]]; then
    log "Installing/Updating dependencies"
    python -m pip install --upgrade pip >/dev/null
    pip install -q -r "$REQ_FILE"
    echo "$NEW_HASH" > "$REQ_HASH_FILE"
  else
    log "Dependencies up-to-date"
  fi
fi

# 4. Load .env (export all defined variables) if present
if [[ -f .env ]]; then
  log "Loading .env"
  set -a; source .env; set +a
fi

# 5. Parameters (override via env vars)
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-1}"
WORKERS="${WORKERS:-1}"

APP_IMPORT_PATH="app.main:app"

CMD=(uvicorn "$APP_IMPORT_PATH" --host "$HOST" --port "$PORT")
if [[ "$RELOAD" == "1" ]]; then
  CMD+=(--reload)
else
  # only apply workers when not in reload mode
  [[ "$WORKERS" -gt 1 ]] && CMD+=(--workers "$WORKERS")
fi

log "Starting server: ${CMD[*]}"
exec "${CMD[@]}"
