from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from typing import Generator, TypedDict
import hashlib
from app.database.database import get_session
from app.database.models import FileORM, JobORM, JobType
from app.database.models import SummaryORM
from app.core.security import get_current_user, UserORM
from app.services.webdav_client import load_webdav_config, write_file_content, get_file_content
from app.core.config import settings

INBOX_DIR = settings.inbox_dir

def _entry_rel_path(name: str) -> str:
    # basic sanitization; replace parent traversal
    safe = name.replace('..', '_').lstrip('/')
    return f"{INBOX_DIR}/{safe}" if INBOX_DIR else safe

router = APIRouter(prefix="/files", tags=["files"])


def session_dep() -> Generator[Session, None, None]:
    with get_session() as s:  # type: ignore[assignment]
        yield s

class FileOut(BaseModel):
    id: int
    original_name: str
    storage_path: str
    mime_type: str | None
    size_bytes: int | None
    sha256: str | None
    model_config = ConfigDict(from_attributes=True)

class FileList(BaseModel):
    total: int
    items: list[FileOut]

class WriteTextIn(BaseModel):
    kind: str
    name: str
    content: str

class ReadQuery(BaseModel):
    kind: str
    name: str

class SummaryOut(BaseModel):
    file_id: int | None
    summary_id: int
    model: str
    summary: str


@router.get("/summaries", response_model=list[SummaryOut], summary="List recent summaries")
async def list_summaries(limit: int = 20, session: Session = Depends(session_dep), user: UserORM = Depends(get_current_user)) -> list[SummaryOut]:
    rows = (
        session.query(SummaryORM)
        .order_by(SummaryORM.id.desc())
        .limit(min(max(limit, 1), 100))
        .all()
    )
    out: list[SummaryOut] = []
    for r in rows:
        out.append(
            SummaryOut(
                file_id=r.file_id,
                summary_id=r.id,
                model="n/a",
                summary=r.summary_text,
            )
        )
    return out

class UploadAccepted(TypedDict, total=False):
    status: str
    file_id: int
    job_id: int

@router.post("/upload", summary="Upload a file", response_model=dict, status_code=202)
async def upload_file(
    file: UploadFile = File(...),
    session: Session = Depends(session_dep),
    user: UserORM = Depends(get_current_user),
) -> UploadAccepted:
    data = await file.read()
    size = len(data)
    sha256 = hashlib.sha256(data).hexdigest()
    # Determine storage path
    storage_name = f"{sha256[:16]}_{file.filename}"
    storage_path = f"{INBOX_DIR}/{storage_name}" if INBOX_DIR else storage_name
    # Check duplicate
    existing = session.query(FileORM).filter(FileORM.sha256 == sha256).first()
    if existing:
        return UploadAccepted(status="duplicate", file_id=existing.id)  # type: ignore[arg-type]
    # Upload to WebDAV
    url, user_nc, password_nc = load_webdav_config()
    import requests
    put_url = f"{url.rstrip('/')}/{storage_path}"
    resp = requests.put(put_url, auth=(user_nc, password_nc), data=data)
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail={"error": {"code": "WEBDAV_UPLOAD_FAILED", "message": resp.text[:200]}})
    f = FileORM(
        original_name=file.filename or storage_name,
        storage_path=storage_path,
        mime_type=file.content_type,
        size_bytes=size,
        sha256=sha256,
    )
    session.add(f)
    session.flush()
    job = JobORM(job_type=JobType.file, file_id=f.id)
    session.add(job)
    session.flush()
    return UploadAccepted(status="accepted", file_id=f.id, job_id=job.id)

@router.get("/", response_model=FileList)
async def list_files(session: Session = Depends(session_dep), user: UserORM = Depends(get_current_user)) -> FileList:
    rows = session.query(FileORM).order_by(FileORM.id.desc()).all()
    out_items = [FileOut.model_validate(r) for r in rows]
    return FileList(total=len(out_items), items=out_items)


class WriteTextOut(BaseModel):
    status: str
    file_id: int


@router.post("/write-file", summary="Write a small text file (kind=entries)", response_model=WriteTextOut)
async def write_text_file(body: WriteTextIn, user: UserORM = Depends(get_current_user), session: Session = Depends(session_dep)) -> WriteTextOut:
    if body.kind != "entries":
        raise HTTPException(status_code=400, detail={"error": {"code": "UNSUPPORTED_KIND", "message": "Only kind=entries supported"}})
    # Simple path policy: entries stored under configured inbox dir
    if len(body.content.encode('utf-8')) > settings.max_text_file_bytes:
        raise HTTPException(status_code=413, detail={"error": {"code": "CONTENT_TOO_LARGE", "message": f"File exceeds {settings.max_text_file_bytes} bytes"}})
    rel_path = _entry_rel_path(body.name)
    try:
        write_file_content(rel_path, body.content)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail={"error": {"code": "WRITE_FAILED", "message": str(exc)}})
    # Create DB record if not exists (hash optional)
    existing = session.query(FileORM).filter(FileORM.storage_path == rel_path).first()
    if not existing:
        f = FileORM(
            original_name=body.name,
            storage_path=rel_path,
            mime_type="text/plain",
            size_bytes=len(body.content.encode("utf-8")),
            sha256=hashlib.sha256(body.content.encode("utf-8")).hexdigest(),
        )
        session.add(f)
        session.flush()
        return WriteTextOut(status="ok", file_id=f.id)
    return WriteTextOut(status="ok", file_id=existing.id)


@router.get("/read-file", summary="Read a text file", response_model=dict)
async def read_text_file(kind: str, name: str, request: Request, user: UserORM = Depends(get_current_user)):
    if kind != "entries":
        raise HTTPException(status_code=400, detail={"error": {"code": "UNSUPPORTED_KIND", "message": "Only kind=entries supported"}})
    rel_path = _entry_rel_path(name)
    try:
        content = get_file_content(rel_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": {"code": "FILE_NOT_FOUND", "message": name}})
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail={"error": {"code": "READ_FAILED", "message": str(exc)}})
    # Compute strong ETag (shortened SHA256) – stable for identical content
    etag = '"' + hashlib.sha256(content.encode('utf-8')).hexdigest()[:32] + '"'
    inm = request.headers.get("if-none-match")
    cache_control = "private, max-age=30"  # short lived client cache OK for read-file
    if inm == etag:
        # Not modified -> 304, empty body
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": cache_control})
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"content": content})
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = cache_control
    return resp


class ListFilesOut(BaseModel):
    total: int
    items: list[FileOut]


@router.get("/list-files", summary="List files (kind=entries)", response_model=ListFilesOut)
async def list_entry_files(kind: str, prefix: str | None = None, limit: int = 100, user: UserORM = Depends(get_current_user), session: Session = Depends(session_dep)) -> ListFilesOut:
    if kind != "entries":
        raise HTTPException(status_code=400, detail={"error": {"code": "UNSUPPORTED_KIND", "message": "Only kind=entries supported"}})
    # Prefilter / safety rule: Force caller to use prefix OR a small limit
    MAX_UNFILTERED = 100
    if not prefix and limit > MAX_UNFILTERED:
        raise HTTPException(status_code=400, detail={"error": {"code": "PREFILTER_REQUIRED", "message": f"Use prefix and/or reduce limit (>{MAX_UNFILTERED}) to narrow results"}})
    like_prefix = f"{INBOX_DIR}/%" if INBOX_DIR else '%'
    q = session.query(FileORM).filter(FileORM.storage_path.like(like_prefix))
    if prefix:
        safe_prefix = prefix.replace('..','_').lstrip('/')
        q = q.filter(FileORM.storage_path.like(f"{INBOX_DIR}/{safe_prefix}%"))
    rows = q.order_by(FileORM.id.desc()).limit(min(max(limit,1),500)).all()
    files = [FileOut.model_validate(r) for r in rows]
    return ListFilesOut(total=len(files), items=files)


class ArchiveIn(BaseModel):
    name: str

class ArchiveOut(BaseModel):
    status: str
    from_path: str
    to_path: str

@router.post("/archive", summary="Move an entry file to archive/", response_model=ArchiveOut)
async def archive_file(body: ArchiveIn, user: UserORM = Depends(get_current_user)) -> ArchiveOut:
    # Only supports files under inbox (kind=entries)
    rel_path = _entry_rel_path(body.name)
    # Validate existence
    try:
        _ = get_file_content(rel_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": {"code": "FILE_NOT_FOUND", "message": body.name}})
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail={"error": {"code": "READ_FAILED", "message": str(exc)}})
    # Compose archive target path
    archive_dir = "BACKBRAIN5.2/archive"
    safe_name = body.name.replace('..','_').lstrip('/')
    target_rel = f"{archive_dir}/{safe_name}".lstrip('/')
    # Perform WebDAV MOVE (atomic on server side) – fallback: read+write+delete if MOVE fails
    url, user_nc, password_nc = load_webdav_config()
    import requests
    src_url = f"{url.rstrip('/')}/{rel_path}"
    dst_url = f"{url.rstrip('/')}/{target_rel}"
    # Ensure archive directory (best-effort)
    try:
        requests.request("MKCOL", f"{url.rstrip('/')}/{archive_dir}", auth=(user_nc, password_nc))
    except Exception:
        pass  # best-effort
    move_headers = {"Destination": dst_url}
    resp = requests.request("MOVE", src_url, headers=move_headers, auth=(user_nc, password_nc))
    if resp.status_code >= 400:
        # Fallback manual copy+delete
        try:
            content = get_file_content(rel_path)
            write_file_content(target_rel, content)
            # delete original
            requests.delete(src_url, auth=(user_nc, password_nc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail={"error": {"code": "ARCHIVE_FAILED", "message": str(exc)}})
    return ArchiveOut(status="archived", from_path=rel_path, to_path=target_rel)
