#!/usr/bin/env python
from __future__ import annotations
import time
import logging
import hashlib
import requests
from sqlalchemy import select
from app.core.config import settings
from app.services.webdav_client import load_webdav_config
from app.database.models import FileORM, JobType
from app.database.database import get_session
from app.database.models import JobORM, JobStatus
from app.services.job_processor import process_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")

POLL_INTERVAL = 2
SCAN_INTERVAL = 10  # seconds between scans of manual_uploads
_last_scan = 0.0

def scan_manual_uploads() -> None:
    global _last_scan
    now = time.time()
    if now - _last_scan < SCAN_INTERVAL:
        return
    _last_scan = now
    manual_dir = settings.manual_uploads_dir.rstrip('/')
    if not manual_dir:
        return
    try:
        base_url, user, pwd = load_webdav_config()
    except Exception as exc:  # pragma: no cover
        logger.warning("manual_scan_config_failed", extra={"error": str(exc)})
        return
    list_url = f"{base_url.rstrip('/')}/{manual_dir}"
    # WebDAV PROPFIND could list; simple heuristic: try GET directory listing (depends on server) -> fallback skip
    # For simplicity we attempt naive file name guesses is out-of-scope; rely on user using flat folder.
    # We'll attempt to fetch an index: many Nextcloud setups forbid; if so abort silently.
    try:
        resp = requests.request("PROPFIND", list_url, auth=(user, pwd), headers={"Depth":"1"}, timeout=10)
        if resp.status_code >= 400:
            return
    except Exception:
        return
    # Extract hrefs (very naive XML parse)
    names: list[str] = []
    for line in resp.text.splitlines():
        if "<d:href>" in line:
            # pull out between tags
            start = line.find('<d:href>') + 8
            end = line.find('</d:href>')
            if end > start:
                href = line[start:end]
                # Expect path ends with /manual_uploads/<file>
                if manual_dir + '/' in href and not href.endswith('/'):
                    candidate = href.split(manual_dir + '/')[1]
                    if '/' not in candidate and candidate:
                        names.append(candidate)
    if not names:
        return
    names = list(set(names))
    with get_session() as session:
        for fname in names:
            storage_path = f"{manual_dir}/{fname}"
            # Fetch file content (text/binary) for hashing and later processing
            try:
                file_url = f"{base_url.rstrip('/')}/{storage_path}"
                fresp = requests.get(file_url, auth=(user, pwd), timeout=20)
                if fresp.status_code == 404:
                    continue
                if fresp.status_code >= 400:
                    logger.warning("manual_fetch_failed", extra={"file": storage_path, "status": fresp.status_code})
                    continue
                data = fresp.content
            except Exception as exc:  # pragma: no cover
                logger.warning("manual_fetch_exc", extra={"file": storage_path, "error": str(exc)})
                continue
            sha256 = hashlib.sha256(data).hexdigest()
            # Deduplicate by sha256 or existing storage path
            existing = session.query(FileORM).filter((FileORM.sha256 == sha256) | (FileORM.storage_path == storage_path)).first()
            if existing:
                continue
            f = FileORM(
                original_name=fname,
                storage_path=storage_path,
                mime_type=None,
                size_bytes=len(data),
                sha256=sha256,
            )
            session.add(f)
            session.flush()
            job = JobORM(job_type=JobType.manual_file, file_id=f.id)
            session.add(job)
            session.flush()
            logger.info("manual_enqueued", extra={"file_id": f.id, "job_id": job.id, "path": storage_path})
            # Move original to archive after enqueue (avoid re-processing)
            archive_dir = "BACKBRAIN5.2/archive"
            try:
                requests.request("MKCOL", f"{base_url.rstrip('/')}/{archive_dir}", auth=(user, pwd), timeout=5)
            except Exception:
                pass
            dst_url = f"{base_url.rstrip('/')}/{archive_dir}/{fname}"
            mv_headers = {"Destination": dst_url}
            mv_resp = requests.request("MOVE", file_url, headers=mv_headers, auth=(user, pwd), timeout=15)
            if mv_resp.status_code >= 400:
                # fallback write new + delete old
                try:
                    requests.put(dst_url, auth=(user, pwd), data=data, timeout=20)
                    requests.delete(file_url, auth=(user, pwd), timeout=10)
                except Exception:
                    logger.warning("manual_archive_fallback_failed", extra={"file": storage_path})
        session.commit()

if __name__ == "__main__":
    logger.info("worker_start")
    while True:
        try:
            # Periodically scan manual uploads
            scan_manual_uploads()
            with get_session() as session:
                stmt = select(JobORM.id).where(JobORM.status.in_([JobStatus.pending, JobStatus.failed])).limit(5)
                jobs = [row[0] for row in session.execute(stmt).all()]
            if not jobs:
                time.sleep(POLL_INTERVAL)
                continue
            for job_id in jobs:
                process_job(job_id)
        except KeyboardInterrupt:  # pragma: no cover
            logger.info("worker_stop")
            break
        except Exception as exc:  # noqa: BLE001
            logger.exception("worker_loop_error", exc_info=exc)
            time.sleep(POLL_INTERVAL)
