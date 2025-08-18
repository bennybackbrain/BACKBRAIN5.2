from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from app.core.config import settings
from app.services.ingest_service import run_scan_cycle, discover_candidates
from typing import Any, Dict

router = APIRouter(prefix="/ingest", tags=["ingest"])  # protected via API key (future enhancement)

def _require_enabled():
    if not settings.auto_ingest_enabled:
        raise HTTPException(status_code=400, detail={"error": {"code": "DISABLED", "message": "auto ingest disabled"}})

@router.post("/scan-now", summary="Trigger on-demand ingest scan", description="Scans drop directories and ingests new files up to the configured per-cycle limit.")
def scan_now(_: Any = Depends(_require_enabled)) -> Dict[str, Any]:  # type: ignore[override]
    return run_scan_cycle()

@router.get("/candidates", summary="List current ingest candidates")
def list_candidates(_: Any = Depends(_require_enabled)) -> Dict[str, Any]:  # type: ignore[override]
    c = discover_candidates()
    return {"count": len(c), "items": [{"dir": d, "name": n} for d, n in c]}

__all__ = ["router"]
