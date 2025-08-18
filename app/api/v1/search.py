from fastapi import APIRouter, Depends, HTTPException, Query
from typing import TypedDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import get_session_dep, get_current_user
from app.database.models import FileORM, SummaryORM

router = APIRouter(prefix="/search", tags=["search"])

@router.get("/files", summary="Simple filename search")
async def search_files(q: str = Query(..., min_length=2, max_length=100), session: Session = Depends(get_session_dep), user=Depends(get_current_user)):
    stmt = select(FileORM).where(FileORM.original_name.ilike(f"%{q}%")).limit(50)
    rows = session.execute(stmt).scalars().all()
    return [{"id": f.id, "name": f.original_name, "path": f.storage_path, "size": f.size_bytes} for f in rows]

class LatestSummaryResp(TypedDict, total=False):
    summary: str | None
    created_at: str

@router.get("/files/{file_id}/latest_summary", summary="Get latest summary for file")
async def latest_summary(file_id: int, session: Session = Depends(get_session_dep), user=Depends(get_current_user)) -> LatestSummaryResp:
    file = session.get(FileORM, file_id)
    if not file:
        raise HTTPException(status_code=404, detail={"error": {"code": "FILE_NOT_FOUND", "message": "File not found"}})
    stmt = select(SummaryORM).where(SummaryORM.file_id == file_id).order_by(SummaryORM.created_at.desc()).limit(1)
    summary = session.execute(stmt).scalars().first()
    if not summary:
        return {"summary": None}
    return {"summary": summary.summary_text, "created_at": summary.created_at.isoformat()}
