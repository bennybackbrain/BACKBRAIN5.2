from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import requests
from app.core.config import settings
from app.core.security import get_current_user
from app.services.webdav_client import list_dir, get_file_content

router = APIRouter(prefix="/webdav", tags=["webdav"])

@router.get("/list", summary="List files in 01_inbox", response_model=list[str])
async def list_inbox(user=Depends(get_current_user)):
    try:
        entries = list_dir("01_inbox")
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail={"error": {"code": "WEBDAV_LIST_FAILED", "message": str(exc)}})
    return entries


@router.get("/read/{file_path:path}", summary="Read a file from WebDAV", response_model=dict)
async def read_file(file_path: str, user=Depends(get_current_user)):
    try:
        content = get_file_content(file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": {"code": "FILE_NOT_FOUND", "message": "File not found"}})
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail={"error": {"code": "WEBDAV_READ_FAILED", "message": str(exc)}})
    return {"content": content}


class WriteFileIn(BaseModel):
    file_path: str = Field(..., description="Relative Pfad inkl. Verzeichnis, z.B. 01_inbox/notiz.txt")
    content: str = Field(..., description="Datei-Inhalt als Text")


@router.post("/write", summary="Write a file via n8n webhook", response_model=dict)
async def write_file(payload: WriteFileIn, user=Depends(get_current_user)):
    webhook = settings.n8n_write_file_webhook_url
    if not webhook:
        raise HTTPException(status_code=500, detail={"error": {"code": "WEBHOOK_NOT_CONFIGURED", "message": "Webhook URL not set"}})
    try:
        resp = requests.post(webhook, json={"file_path": payload.file_path, "content": payload.content}, timeout=15)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail={"error": {"code": "WEBHOOK_CALL_FAILED", "message": str(exc)}})
    # Forward response
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail={"error": {"code": "WEBHOOK_ERROR", "message": resp.text}})
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}
    return {"status": "ok", "upstream": data}
