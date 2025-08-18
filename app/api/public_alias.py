"""Public (unauthenticated) alias endpoints.

Option B: expose simplified routes without auth so a lightweight external
client (e.g. GPT Action prototype) can call them without JWT / API Key.

WARNING: These endpoints bypass authentication. Use only in controlled
environments or behind an external auth / gateway if exposed publicly.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
import os
from typing import Any  # dynamic layers
import os
import logging
from pydantic import BaseModel
from typing import List
import hashlib
from app.core.config import get_settings
from app.database.database import get_session
from app.database.models import FileORM, SummaryORM
from app.services.webdav_client import get_file_content, write_file_content, list_dir, mkdirs
from app.api.v1.files import _entry_rel_path  # type: ignore  # internal helper reuse
from app.core import metrics
from collections import deque
from pathlib import Path
import time
import threading
import time
from app.core.metrics import auto_summary_total, auto_summary_duration_seconds
from typing import Deque, Dict

router = APIRouter()
log = logging.getLogger("public_alias")

# Dynamic placeholders for optional external helpers (silence type noise)
db: Any  # noqa: ANN401
webdav: Any  # noqa: ANN401

# Cap for summaries endpoint (env override, hard limit 1000)
try:
    _max_summaries_env = int(os.getenv("MAX_SUMMARIES", "500"))
except ValueError:  # pragma: no cover
    _max_summaries_env = 500
MAX_SUMMARIES = max(1, min(_max_summaries_env, 1000))

def _list_files_webdav(dir_path: str) -> list[str]:
    """List files in WebDAV directory returning simple basenames, sorted."""
    try:
        try:
            mkdirs(dir_path)
        except Exception:
            pass
        raw = list_dir(dir_path)
    except Exception:
        return []
    names: list[str] = []
    for n in raw:
        bn = n.rsplit('/', 1)[-1]
        if not bn or bn.endswith('/'):
            continue
        names.append(bn)
    return sorted(names)

def _read_text_webdav(rel_path: str) -> str:
    try:
        return get_file_content(rel_path)
    except Exception:
        return ""

# Local fallback root used when WebDAV operations fail (see write-file route)
LOCAL_FALLBACK_ROOT = Path("public_fallback")

def _list_local_fallback(kind: str) -> list[str]:
    """List files saved via local fallback (non-WebDAV) storage.

    Returns basenames sorted newest-first by mtime.
    """
    try:
        root = LOCAL_FALLBACK_ROOT / ("entries" if kind == "entries" else "summaries")
        if not root.exists() or not root.is_dir():
            return []
        items: list[tuple[str, float]] = []
        for p in root.iterdir():
            if p.is_file():
                try:
                    items.append((p.name, float(p.stat().st_mtime)))
                except Exception:
                    items.append((p.name, 0.0))
        items.sort(key=lambda t: t[1], reverse=True)
        return [n for (n, _) in items[:500]]
    except Exception:
        return []

## (Removed duplicate MAX_SUMMARIES and helper definitions)


class FileListResponse(BaseModel):
    kind: str
    files: List[str]


class ReadFileResponse(BaseModel):
    name: str
    kind: str
    content: str


class WriteFileRequest(BaseModel):
    name: str
    kind: str
    content: str


class WriteFileResponse(BaseModel):
    status: str
    name: str
    kind: str


class SummaryItem(BaseModel):
    name: str
    content: str


class AllSummariesResponse(BaseModel):
    summaries: List[SummaryItem]


@router.get("/list-files")
@router.get(
    "/list-files/",
    response_model=FileListResponse,
    tags=["public"],
    summary="List recent entry or summary filenames",
    operation_id="listFiles",
    description="Returns up to 500 newest file names for the given kind (entries|summaries)."
)
def public_list_files(kind: str, request: Request = None):  # type: ignore[override]
    settings = get_settings()
    if kind not in ("entries", "summaries"):
        raise HTTPException(status_code=400, detail="invalid kind")
    files: list[str] = []
    degraded = False
    db_rows = 0
    webdav_disabled = os.getenv("WEBDAV_DISABLED", "").lower() in {"1", "true", "yes"}
    try:
        with get_session() as s:  # type: ignore[assignment]
            if kind == "entries":
                like_prefix = f"{settings.inbox_dir}/%"
                rows = (s.query(FileORM)  # type: ignore[attr-defined]
                        .filter(FileORM.storage_path.like(like_prefix))  # type: ignore[attr-defined]
                        .order_by(FileORM.id.desc())  # type: ignore[attr-defined]
                        .limit(500)
                        .all())
                db_rows = len(rows)
                files.extend([r.original_name for r in rows])
            else:
                rows = (s.query(SummaryORM)  # type: ignore[attr-defined]
                        .order_by(SummaryORM.id.desc())  # type: ignore[attr-defined]
                        .limit(500)
                        .all())
                db_rows = len(rows)
                file_ids = {r.file_id for r in rows if r.file_id}
                file_map = {}
                if file_ids:
                    for fr in s.query(FileORM).filter(FileORM.id.in_(file_ids)).all():  # type: ignore[arg-type,attr-defined]
                        file_map[fr.id] = fr.original_name
                for r in rows:
                    files.append(file_map.get(r.file_id, f"summary_{r.id}"))
    except Exception as exc:  # pragma: no cover
        degraded = True
        log.warning("public_list_files_degraded_db", extra={"kind": kind, "error": str(exc)})
    # Fallback: if entries and DB empty OR degraded -> attempt WebDAV directory listing
    if not webdav_disabled:
        try:
            if kind == "entries" and (degraded or db_rows == 0):
                base = settings.inbox_dir
                if base:
                    # ensure directory (best-effort)
                    try:
                        mkdirs(base)
                    except Exception:
                        pass
                    raw = list_dir(base)
                    web_files: list[str] = []
                    for e in raw:
                        name = e.rsplit('/', 1)[-1]
                        if not name or name.endswith('/'):
                            continue
                        web_files.append(name)
                    if web_files:
                        # Replace only if we actually found something
                        files = sorted(set(files) | set(web_files), reverse=True)[:500]
                        log.info("public_list_files_webdav_fallback", extra={"kind": kind, "count": len(files), "db_rows": db_rows})
        except Exception as exc:  # pragma: no cover
            log.warning("public_list_files_webdav_fallback_failed", extra={"error": str(exc)})
    # Local fallback enumeration (only if still empty)
    if not files:
        lf = _list_local_fallback(kind)
        if lf:
            files = lf
    resp = FileListResponse(kind=kind, files=files)
    try:
        client_ip = request.client.host if request and request.client else 'unknown'
        log.info("public_list_files", extra={"kind": kind, "count": len(files), "ip": client_ip})
    # request metrics collected centrally
    except Exception:
        pass
    # Attach degraded hint header if response object available via dependency (not here), else just return
    if request is not None:
        try:
            # FastAPI will set headers on Response object; we create a simple attribute hack via state (not critical)
            if degraded and hasattr(request, 'state'):
                setattr(request.state, 'x_degraded_list', 'true')  # marker (not automatically serialized)
        except Exception:
            pass
    return resp


@router.get("/read-file")
@router.get(
    "/read-file/",
    response_model=ReadFileResponse,
    tags=["public"],
    summary="Read a stored file (entry or summary)",
    operation_id="readFile",
    description="Reads full text content. Supports ETag via If-None-Match for caching. kind defaults to 'entries'."
)
def public_read_file(name: str, kind: str = "entries", request: Request = None, response: Response = None):  # type: ignore[assignment]
    settings = get_settings()
    if kind not in ("entries", "summaries"):
        raise HTTPException(status_code=400, detail="invalid kind")
    if kind == "entries":
        rel_path = _entry_rel_path(name)
    else:
        safe = name.replace('..', '_').lstrip('/')
        rel_path = f"{settings.summaries_dir}/{safe}" if settings.summaries_dir else safe
    content = None
    webdav_disabled = os.getenv("WEBDAV_DISABLED", "").lower() in {"1", "true", "yes"}
    etag: str | None = None
    attempted_remote = False
    if not webdav_disabled:
        try:
            content = get_file_content(rel_path)
            attempted_remote = True
            etag = hashlib.sha256(content.encode('utf-8')).hexdigest()
            inm = request.headers.get('if-none-match') if request else None  # type: ignore[union-attr]
            cache_bust = request.query_params.get('cb') if request else None  # type: ignore[union-attr]
            if not cache_bust and inm and inm.strip('"') == etag:
                if response is not None:
                    response.status_code = 304
                    response.headers['ETag'] = f'"{etag}"'
                    response.headers['Cache-Control'] = 'private, max-age=30'
                return ReadFileResponse(name=name, kind=kind, content="")
            if response is not None:
                response.headers['ETag'] = f'"{etag}"'
                response.headers['Cache-Control'] = 'private, max-age=30'
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="not found")
        except Exception:
            # Will fallback to local below
            content = None
    if content is None:
        # Local fallback read
        fallback_file = LOCAL_FALLBACK_ROOT / ("entries" if kind == "entries" else "summaries") / name
        if fallback_file.exists():
            content = fallback_file.read_text(encoding="utf-8", errors="replace")
            etag = hashlib.sha256(content.encode('utf-8')).hexdigest()
            if response is not None:
                response.headers['ETag'] = f'"{etag}"'
                response.headers['Cache-Control'] = 'private, max-age=30'
            # Conditional match check (only if remote was attempted or webdav disabled)
            inm = request.headers.get('if-none-match') if request else None  # type: ignore[union-attr]
            cache_bust = request.query_params.get('cb') if request else None  # type: ignore[union-attr]
            if not cache_bust and inm and etag and inm.strip('"') == etag:
                if response is not None:
                    response.status_code = 304
                return ReadFileResponse(name=name, kind=kind, content="")
        else:
            # Nothing found anywhere
            if attempted_remote:
                raise HTTPException(status_code=404, detail="not found")
            raise HTTPException(status_code=502, detail="unavailable")
    # Optional gzip (base64) if client accepts and large content
    content_out = content
    if request and 'gzip' in request.headers.get('accept-encoding', '').lower() and len(content) > 2048:
        try:
            import gzip, base64
            gz = gzip.compress(content.encode('utf-8'))
            content_out = 'gzip64:' + base64.b64encode(gz).decode('ascii')
        except Exception:
            pass
    out = ReadFileResponse(name=name, kind=kind, content=content_out)
    try:
        log.info("public_read_file", extra={"name": name, "kind": kind, "size": len(content)})
    except Exception:
        pass
    return out

@router.post("/write-file")
@router.post(
    "/write-file/",
    response_model=WriteFileResponse,
    tags=["public"],
    summary="Create or overwrite a text entry or summary file",
    operation_id="writeFile",
    description="Writes UTF-8 text. Rejects if > max_text_file_bytes. Sets ETag header. If identical content exists returns status=unchanged."
)
def public_write_file(body: WriteFileRequest, request: Request, response: Response):  # type: ignore[assignment]
    settings = get_settings()
    if not settings.public_write_enabled:
        raise HTTPException(status_code=403, detail="public write disabled")
    # Per-app, per-IP minute window limiter using app.state
    if settings.public_writefile_limit_per_minute > 0:
        store: Dict[str, Deque[float]] = getattr(request.app.state, 'public_write_buckets', None)  # type: ignore[attr-defined]
        if store is None:
            store = {}
            setattr(request.app.state, 'public_write_buckets', store)  # type: ignore[attr-defined]
        ip = request.client.host if request.client else 'unknown'
        dq = store.get(ip)
        if dq is None:
            dq = deque()  # type: ignore[var-annotated]
            store[ip] = dq
        now = time.time()
        while dq and now - dq[0] > 60:
            dq.popleft()
        if len(dq) >= settings.public_writefile_limit_per_minute:
            try:
                metrics.write_file_errors_total.inc()
            except Exception:
                pass
            log.info("public_write_file_rate_limited", extra={"ip": ip, "count": len(dq)})
            raise HTTPException(status_code=429, detail='public write limit reached')
        dq.append(now)
        try:
            metrics.write_file_total.inc()
        except Exception:
            pass
        try:
            response.headers['X-Public-Write-Count'] = str(len(dq))
            response.headers['X-Public-Write-Limit'] = str(settings.public_writefile_limit_per_minute)
            response.headers['X-Public-Write-IPs'] = str(len(store))
        except Exception:
            pass
    if body.kind not in ("entries", "summaries"):
        raise HTTPException(status_code=400, detail="invalid kind")
    content_bytes = body.content.encode("utf-8")
    if len(content_bytes) > settings.max_text_file_bytes:
        raise HTTPException(status_code=413, detail="too large")
    if body.kind == "entries":
        rel_path = _entry_rel_path(body.name)
        try:
            parent = rel_path.rsplit('/', 1)[0]
            if parent:
                mkdirs(parent)
        except Exception:
            pass
    else:
        safe = body.name.replace('..', '_').lstrip('/')
        rel_path = f"{settings.summaries_dir}/{safe}" if settings.summaries_dir else safe
        try:
            parent = rel_path.rsplit('/', 1)[0]
            if parent:
                mkdirs(parent)
        except Exception:
            pass
    existing_content = None
    try:
        existing_content = get_file_content(rel_path)
    except Exception:
        existing_content = None
    status = "saved"
    storage_mode = "webdav"
    try:
        if existing_content is not None and existing_content == body.content:
            status = "unchanged"
        else:
            write_file_content(rel_path, body.content)
    except Exception as exc:  # pragma: no cover
        try:
            fallback_root = Path("public_fallback") / ("entries" if body.kind == "entries" else "summaries")
            fallback_root.mkdir(parents=True, exist_ok=True)
            local_path = fallback_root / body.name
            local_path.write_text(body.content, encoding="utf-8")
            storage_mode = "local-fallback"
            status = "saved" if status != "unchanged" else status
            log.warning("public_write_file_fallback", extra={"path": str(local_path), "reason": str(exc)})
        except Exception as exc2:
            raise HTTPException(status_code=502, detail=f"write failed: {exc2}")
    file_record_id = None
    if body.kind == "entries" and storage_mode != "local-fallback":
        try:
            with get_session() as s:  # type: ignore[assignment]
                existing = s.query(FileORM).filter(FileORM.storage_path == rel_path).first()  # type: ignore[attr-defined]
                if existing:
                    file_record_id = existing.id
                else:
                    f = FileORM(
                        original_name=body.name,
                        storage_path=rel_path,
                        mime_type="text/plain",
                        size_bytes=len(content_bytes),
                        sha256=hashlib.sha256(content_bytes).hexdigest(),
                    )
                    s.add(f)
                    s.flush()  # assign id
                    file_record_id = f.id
        except Exception as db_exc:  # pragma: no cover
            log.warning("public_write_file_db_skip", extra={"error": str(db_exc)})

    # Background auto-summary generation (heuristic or OpenAI depending on config)
    def _bg_generate_summary(file_id: int | None, original_name: str, content: str, storage: str = "unknown"):  # pragma: no cover - non-deterministic timing
        t0 = time.perf_counter()
        try:
            log.info("auto_summary_start", extra={"file": original_name, "storage": storage})
        except Exception:
            pass
        try:
            from app.services.summarizer import summarize_text
            res = summarize_text(content, file_name=original_name, source="public_write")
            summary_text = res.summary
            # Persist DB row if file_id available
            if file_id is not None:
                try:
                    with get_session() as s:  # type: ignore[assignment]
                        s.add(SummaryORM(file_id=file_id, summary_text=summary_text))  # type: ignore[arg-type]
                except Exception as exc_db:  # pragma: no cover
                    log.warning("auto_summary_db_fail", extra={"error": str(exc_db)})
            # Write summary artifact to summaries_dir if configured
            wrote_storage = storage
            try:
                settings_local = get_settings()
                summary_name = f"{original_name}.summary.md"
                if settings_local.summaries_dir:
                    summary_rel = f"{settings_local.summaries_dir}/{summary_name}"
                    try:
                        write_file_content(summary_rel, summary_text)
                        wrote_storage = "webdav"
                    except Exception as webdav_exc:  # pragma: no cover
                        # local fallback
                        try:
                            fb_root = LOCAL_FALLBACK_ROOT / "summaries"
                            fb_root.mkdir(parents=True, exist_ok=True)
                            (fb_root / summary_name).write_text(summary_text, encoding="utf-8")
                            wrote_storage = "local-fallback"
                            log.warning("auto_summary_local_fallback", extra={"file": summary_name, "reason": str(webdav_exc)})
                        except Exception:
                            pass
            except Exception as exc_any:  # pragma: no cover
                log.warning("auto_summary_write_fail", extra={"error": str(exc_any)})
            # Metrics success
            try:
                auto_summary_total.labels(status="ok", storage=wrote_storage or storage).inc()
                auto_summary_duration_seconds.observe(time.perf_counter() - t0)
            except Exception:  # pragma: no cover
                pass
            try:
                log.info("public_write_file_summary_created", extra={"file": original_name, "model": res.model, "chars": len(summary_text), "storage": wrote_storage})
            except Exception:
                pass
        except Exception as exc:  # pragma: no cover
            try:
                auto_summary_total.labels(status="error", storage=storage).inc()
                auto_summary_duration_seconds.observe(time.perf_counter() - t0)
            except Exception:  # pragma: no cover
                pass
            log.warning("auto_summary_failed", extra={"error": str(exc), "file": original_name, "storage": storage})

    # Spawn thread only if this was a real save (not unchanged) and we have entry content
    if body.kind == "entries" and status != "unchanged":
        try:
            # type: ignore[arg-type] - dynamic logging extras fine
            log.info("public_write_file_summary_thread_start", extra={"file": body.name, "file_id": file_record_id})
            threading.Thread(target=_bg_generate_summary, args=(file_record_id, body.name, body.content, storage_mode), daemon=True).start()
        except Exception:  # pragma: no cover
            pass
    etag = hashlib.sha256(body.content.encode('utf-8')).hexdigest()
    response.headers['ETag'] = f'"{etag}"'
    response.headers['X-Deduplicated'] = 'true' if status == 'unchanged' else 'false'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Storage'] = storage_mode
    out = WriteFileResponse(status=status, name=body.name, kind=body.kind)
    try:
        client_ip = request.client.host if request and request.client else 'unknown'
        log.info("public_write_file", extra={"name": body.name, "kind": body.kind, "status": status, "bytes": len(content_bytes), "ip": client_ip})
    except Exception:
        pass
    return out


@router.get(
    "/get_all_summaries",
    response_model=AllSummariesResponse,
    tags=["public"],
    summary="Return recent summaries with their text",
    operation_id="getAllSummaries",
    description="DB-first with WebDAV fallback. Always 200. Capped via MAX_SUMMARIES."
)
def get_all_summaries():  # type: ignore[override]
    """Defensive summaries endpoint.

    1) Try dynamic db.list_summaries() if provided (returns iterable of dict-like) else ORM fallback.
    2) If empty/error -> WebDAV fallback.
    3) Always 200; never raises.
    4) Truncates each summary text to 300 chars and caps total items by MAX_SUMMARIES.
    """
    # 1) DB first (dynamic helper)
    try:  # pragma: no cover - dynamic path
        if 'db' in globals() and hasattr(db, 'list_summaries'):
            rows = db.list_summaries()  # type: ignore[attr-defined]
            if rows:
                summaries = [
                    {"name": (r.get("name") or ""), "content": (r.get("summary") or "")[:300]}
                    for r in rows
                ]
                return AllSummariesResponse(summaries=[SummaryItem(name=s["name"], content=s["content"]) for s in summaries[:MAX_SUMMARIES]])
    except Exception:
        log.exception("db_list_summaries_failed")

    # ORM fallback
    try:
        with get_session() as s:  # type: ignore[assignment]
            rows = (s.query(SummaryORM)  # type: ignore[attr-defined]
                    .order_by(SummaryORM.id.desc())  # type: ignore[attr-defined]
                    .limit(MAX_SUMMARIES)
                    .all())
            file_ids = {r.file_id for r in rows if r.file_id}  # type: ignore[misc]
            file_map: dict[int, str] = {}
            if file_ids:
                for fr in s.query(FileORM).filter(FileORM.id.in_(file_ids)).all():  # type: ignore[arg-type]
                    file_map[fr.id] = fr.original_name  # type: ignore[attr-defined]
            summaries = [
                {"name": file_map.get(r.file_id, f"summary_{r.id}"), "content": r.summary_text[:300]}
                for r in rows  # type: ignore[misc]
            ]
            if summaries:
                return AllSummariesResponse(summaries=[SummaryItem(name=s["name"], content=s["content"]) for s in summaries[:MAX_SUMMARIES]])
    except Exception:
        log.exception("orm_list_summaries_failed")

    # 2) WebDAV fallback
    settings = get_settings()
    names = _list_files_webdav(settings.summaries_dir)
    out = []
    for name in names[:MAX_SUMMARIES]:
        text = _read_text_webdav(f"{settings.summaries_dir}/{name}")
        if text:
            out.append({"name": name, "content": text[:300]})
    return AllSummariesResponse(summaries=[SummaryItem(name=s["name"], content=s["content"]) for s in out])

# Backward compatibility alias for older test name
public_get_all_summaries = get_all_summaries  # type: ignore

# Simple alias expected by some docs/snippets
def list_files(kind: str):  # pragma: no cover - thin wrapper
    return public_list_files(kind=kind)


@router.get("/diag/storage", tags=["public"], summary="Diagnostic storage paths (public)")
def public_diag_storage(request: Request = None):  # type: ignore[override]
    """Lightweight diagnostic: returns configured directories.

    Purpose: quickly confirm path alignment (inbox vs summaries) for troubleshooting list-files mismatches.
    Safe because it discloses only directory configuration already implied by filenames.
    """
    try:
        settings = get_settings()
        data = {
            "inbox_dir": settings.inbox_dir,
            "summaries_dir": settings.summaries_dir,
        }
    except Exception as exc:  # pragma: no cover
        data = {"error": str(exc)}
    try:
        client_ip = request.client.host if request and request.client else 'unknown'
        log.info("public_diag_storage", extra={"ip": client_ip})
    except Exception:
        pass
    return data

__all__ = ["router"]

# (Buckets now stored per FastAPI app instance in app.state.public_write_buckets)
