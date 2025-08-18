#!/usr/bin/env bash
set -euo pipefail
STAMP="$(date +%F-%H%M%S)"
mkdir -p backups
OUT="backups/backbrain_${STAMP}.tgz"

tar -czf "$OUT" backbrain.db || {
  echo "WARN: backbrain.db not found, skipping DB archive" >&2
}

echo "Local backup: $OUT"

if [[ -n "${WEBDAV_URL:-}" && -n "${WEBDAV_USERNAME:-}" && -n "${WEBDAV_PASSWORD:-}" ]]; then
  TARGET_PATH="${WEBDAV_URL%/}/BACKBRAIN5.2/backups/$(basename "$OUT")"
  echo "Uploading to WebDAV: $TARGET_PATH" >&2
  curl -fsS -u "$WEBDAV_USERNAME:$WEBDAV_PASSWORD" -T "$OUT" "$TARGET_PATH" || echo "Upload failed" >&2
fi

# Retention (keep last 20 local backups)
ls -1t backups/backbrain_*.tgz 2>/dev/null | tail -n +21 | xargs -r rm -f
