#!/usr/bin/env bash
set -euo pipefail
# Mirror BACKBRAIN critical folders from WebDAV (Nextcloud) to local backup tree.
# Requires prior rclone remote: backbrainwebdav (type webdav, vendor nextcloud)
# Environment: optional BACKUP_ROOT (default backups/backbrain)

BACKUP_ROOT=${BACKUP_ROOT:-backups/backbrain}
mkdir -p "$BACKUP_ROOT/01_inbox" "$BACKUP_ROOT/summaries"

log(){ printf '[%s] %s\n' "$(date -Iseconds)" "$*"; }

SRC_INBOX="backbrainwebdav:BACKBRAIN5.2/01_inbox"
SRC_SUMMARIES="backbrainwebdav:BACKBRAIN5.2/summaries"

log "Sync inbox -> $BACKUP_ROOT/01_inbox"
rclone sync "$SRC_INBOX" "$BACKUP_ROOT/01_inbox" --create-empty-src-dirs
log "Sync summaries -> $BACKUP_ROOT/summaries"
rclone sync "$SRC_SUMMARIES" "$BACKUP_ROOT/summaries" --create-empty-src-dirs

log "Done."
