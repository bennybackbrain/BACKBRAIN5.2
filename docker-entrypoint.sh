#!/usr/bin/env bash
set -euo pipefail

# Run migrations if enabled
if [[ "${DO_MIGRATE:-1}" == "1" ]]; then
  echo "[entrypoint] Applying migrations..."
  alembic upgrade head || { echo "Migration failed"; exit 1; }
else
  echo "[entrypoint] Skipping migrations (DO_MIGRATE=${DO_MIGRATE})"
fi

exec "$@"
