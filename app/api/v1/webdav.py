from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Form
from pydantic import BaseModel, Field
from typing import Optional
from app.core.config import settings
from app.core.security import get_current_user, UserORM
from app.services.webdav_client import list_dir, get_file_content, write_file_content, mkdirs
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/webdav", tags=["webdav"])

@router.get("/list", summary="List files in inbox", response_model=list[str])
async def list_inbox(user: UserORM = Depends(get_current_user)):
    try:
        return list_dir(settings.inbox_dir)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail={"error": {"code": "WEBDAV_LIST_FAILED", "message": str(exc)}})


@router.get("/read/{file_path:path}", summary="Read a file from WebDAV", response_model=dict)
async def read_file(file_path: str, user: UserORM = Depends(get_current_user)):
    try:
        content = get_file_content(file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": {"code": "FILE_NOT_FOUND", "message": "File not found"}})
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail={"error": {"code": "WEBDAV_READ_FAILED", "message": str(exc)}})
    return {"content": content}


class WriteFileIn(BaseModel):
    file_path: str = Field(..., description="Relative Pfad inkl. Verzeichnis, z.B. <inbox_dir>/notiz.txt")
    content: str = Field(..., description="Datei-Inhalt als Text")




class MkdirIn(BaseModel):
    path: str = Field(..., description="Verzeichnis (relativ) das angelegt werden soll")

def _normalize_path(p: str) -> str:
    p = p.strip().strip('/')
    if not p:
        raise HTTPException(status_code=422, detail={"error": {"code": "PATH_REQUIRED", "message": "path is required"}})
    if '..' in p.split('/'):
        raise HTTPException(status_code=400, detail={"error": {"code": "INVALID_PATH", "message": "no parent traversal"}})
    while '//' in p:
        p = p.replace('//', '/')
    return p


@router.post("/mkdir", summary="Create directory (JSON or query path)")
async def mkdir(body: Optional[MkdirIn] = None, path: Optional[str] = Query(None), user: UserORM = Depends(get_current_user)):
    target = (body.path if body and body.path else path) or ''
    target = _normalize_path(target)
    try:
        created = mkdirs(target)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail={"error": {"code": "WEBDAV_MKDIR_FAILED", "message": str(exc)}})
    status_code = 201 if created else 200
    return JSONResponse({"ok": True, "path": target, "created": created}, status_code=status_code)


class DirectWriteIn(BaseModel):
    path: str = Field(..., description="Ziel-Dateipfad relativ zum Root")
    content: str = Field(..., description="Inhalt")


@router.post("/put", summary="Write file directly to WebDAV", response_model=dict)
async def put_file(payload: DirectWriteIn, user: UserORM = Depends(get_current_user)):
    try:
        write_file_content(payload.path, payload.content)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail={"error": {"code": "WEBDAV_WRITE_FAILED", "message": str(exc)}})
    return {"status": "ok", "path": payload.path}

@router.post("/mkdir-form", summary="Create directory via form")
async def mkdir_form(path: str = Form(...), user: UserORM = Depends(get_current_user)):
    return await mkdir(body=None, path=path, user=user)  # type: ignore[arg-type]

@router.get("/mkdir", summary="Create directory via GET (idempotent)")
async def mkdir_get(path: str = Query(...), user: UserORM = Depends(get_current_user)):
    return await mkdir(body=None, path=path, user=user)  # type: ignore[arg-type]
