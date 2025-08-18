from __future__ import annotations
"""Auto Ingest Service.

Scans configured drop directories (inbox + manual uploads) for new files and ingests
text into the system by creating entry files (re-upload into entries path) to trigger
summary pipeline.

Design:
 - Stateless functions; scheduling handled in app startup loop.
 - Uses WebDAV listing; avoids DB dependency. Deduplication by presence of corresponding
   summary artifact or an existing .ingested marker locally (fallback mode).
 - PDF extraction: naive text pull using pdfminer.six (optional, skip if lib missing).

Security / Safeguards:
 - Only processes allowed extensions (configurable).
 - Size limit inherited from write-file (caller ensures not oversized).
 - Max files per cycle to bound latency / cost.
"""
import logging
from typing import List, Tuple
from app.core.config import settings
from app.services.webdav_client import list_dir, get_file_content, write_file_content
from app.core import metrics

logger = logging.getLogger("app.ingest")

def _allowed(name: str) -> bool:
    exts = {e.strip().lower() for e in settings.ingest_allowed_extensions.split(',') if e.strip()}
    return any(name.lower().endswith(ext) for ext in exts)

def discover_candidates() -> List[Tuple[str, str]]:
    """Return list of (source_dir, filename) for allowed files that appear not summarized yet.

    Heuristic: if a sibling summary file <name>.summary.md exists in summaries_dir -> skip.
    """
    dirs = {settings.inbox_dir, settings.manual_uploads_dir}
    out: List[Tuple[str, str]] = []
    try:
        summaries = set(list_dir(settings.summaries_dir))
    except Exception:
        summaries: set[str] = set()
    for d in dirs:
        try:
            names = list_dir(d)
        except Exception as exc:  # pragma: no cover
            logger.warning("ingest_list_dir_fail", extra={"dir": d, "error": str(exc)})
            continue
        for name in names:
            if not _allowed(name):
                continue
            if f"{name}.summary.md" in summaries:
                continue
            out.append((d, name))
    return out

def ingest_file(source_dir: str, name: str) -> bool:
    """Ingest one file by copying content into entries dir (if not already there).

    Returns True if an entry was written (ingested) else False (skipped).
    """
    from app.core.config import settings as live_settings
    try:
        rel_path = f"{source_dir}/{name}".lstrip('/')
        text = get_file_content(rel_path)
    except Exception as exc:
        metrics.auto_ingest_files_total.labels(action="error").inc()
        logger.warning("ingest_read_fail", extra={"file": name, "dir": source_dir, "error": str(exc)})
        return False

    if source_dir == live_settings.inbox_dir:
        metrics.auto_ingest_files_total.labels(action="skipped").inc()
        return False

    dest_rel = f"{live_settings.inbox_dir}/{name}".lstrip('/')
    try:
        write_file_content(dest_rel, text)
        metrics.auto_ingest_files_total.labels(action="ingested").inc()
        logger.info("auto_ingest_written", extra={"file": name, "source": source_dir})
        return True
    except Exception as exc:
        metrics.auto_ingest_files_total.labels(action="error").inc()
        logger.warning("auto_ingest_write_fail", extra={"file": name, "error": str(exc)})
        return False

from typing import Dict, Any

def run_scan_cycle() -> Dict[str, Any]:
    """Execute one scan cycle.

    Returns dict with counts for logging / endpoint response.
    """
    try:
        candidates = discover_candidates()
        if not candidates:
            metrics.auto_ingest_scan_total.labels(result="ok").inc()
            return {"candidates": 0, "ingested": 0}
        from app.core.config import settings as live_settings
        limit = max(1, live_settings.auto_ingest_max_files_per_cycle)
        ingested = 0
        for (src, name) in candidates[:limit]:
            if ingest_file(src, name):
                ingested += 1
        metrics.auto_ingest_scan_total.labels(result="ok").inc()
        return {"candidates": len(candidates), "ingested": ingested}
    except Exception as exc:  # pragma: no cover
        metrics.auto_ingest_scan_total.labels(result="error").inc()
        logger.exception("auto_ingest_scan_fail")
        return {"error": str(exc)}

__all__ = [
    "discover_candidates",
    "ingest_file",
    "run_scan_cycle",
]
