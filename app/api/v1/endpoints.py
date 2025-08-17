from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import BackgroundTasks
import logging
from pydantic import BaseModel, ConfigDict
from typing import List
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.database import get_session
from app.database.models import EntryORM, JobORM, JobStatus
from app.core.security import get_current_user
from app.services.job_processor import process_job

router = APIRouter(prefix="/entries")


class EntryIn(BaseModel):
    text: str

    # Examples to appear in OpenAPI schema
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"text": "Notiz über ein neues Feature"},
                {"text": "Idee: Embeddings für Ähnlichkeit"},
            ]
        }
    )


class EntryOut(BaseModel):
    id: int
    text: str

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {"id": 1, "text": "Notiz über ein neues Feature"},
                {"id": 42, "text": "Idee: Embeddings für Ähnlichkeit"},
            ]
        },
    )


def session_dep():
    with get_session() as s:  # generator style for dependency
        yield s


class EntriesPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[EntryOut]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "total": 27,
                    "limit": 10,
                    "offset": 0,
                    "items": [
                        {"id": 1, "text": "Notiz über ein neues Feature"},
                        {"id": 2, "text": "Idee: Embeddings für Ähnlichkeit"},
                    ],
                }
            ]
        }
    )


class ErrorItem(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorItem

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"error": {"code": "ENTRY_NOT_FOUND", "message": "Entry not found"}},
                {"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed"}},
            ]
        }
    )


class ValidationIssue(BaseModel):
    loc: List[str | int]
    msg: str
    type: str


class ValidationErrorResponse(ErrorResponse):
    details: List[ValidationIssue]  # type: ignore[assignment]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed"},
                    "details": [
                        {"loc": ["body", "entry", "text"], "msg": "Field required", "type": "missing"}
                    ],
                }
            ]
        }
    )


@router.get(
    "/",
    response_model=EntriesPage,
    summary="List entries",
    description=(
        "Gibt eine paginierte Liste aller gespeicherten Einträge zurück. "
        "Parameter 'limit' bestimmt die maximale Anzahl (1-100), 'offset' überspringt eine Anzahl von Einträgen."
    ),
    tags=["entries"],
    responses={
        422: {
            "model": ValidationErrorResponse,
            "description": "Validierungsfehler in Query-Parametern",
        }
    },
)
async def list_entries(
    limit: int = Query(10, ge=1, le=100, description="Max entries to return"),
    offset: int = Query(0, ge=0, description="Number of entries to skip"),
    session: Session = Depends(session_dep),
    user=Depends(get_current_user),
):
    total = session.query(func.count(EntryORM.id)).scalar() or 0
    query = session.query(EntryORM).order_by(EntryORM.id.asc()).offset(offset).limit(limit)
    rows = query.all()
    logging.getLogger("app.entries").info(
        "entries_listed",
        extra={"count": len(rows), "total": total, "limit": limit, "offset": offset},
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": rows,
    }


class JobAccepted(BaseModel):
    job_id: int
    status: JobStatus

    model_config = ConfigDict(json_schema_extra={"example": {"job_id": 1, "status": "pending"}})


@router.post(
    "/",
    response_model=JobAccepted,
    status_code=202,
    summary="Create entry (async)",
    description="Legt einen neuen Verarbeitungs-Job an und gibt sofort eine Job-ID zurück (Status pending).",
    tags=["entries"],
    responses={
        202: {"description": "Job angenommen"},
        422: {
            "model": ValidationErrorResponse,
            "description": "Body-Validierung fehlgeschlagen",
        }
    },
)
async def create_entry(
    entry: EntryIn,
    background_tasks: BackgroundTasks,
    session: Session = Depends(session_dep),
    user=Depends(get_current_user),
):
    job = JobORM(input_text=entry.text)
    session.add(job)
    session.flush()
    logging.getLogger("app.entries").info("job_enqueued", extra={"job_id": job.id})
    background_tasks.add_task(process_job, job.id)
    return {"job_id": job.id, "status": job.status}


@router.get(
    "/{entry_id}",
    response_model=EntryOut,
    summary="Get entry",
    description="Lädt einen einzelnen Eintrag anhand seiner ID.",
    tags=["entries"],
    responses={
        404: {"model": ErrorResponse, "description": "Eintrag nicht gefunden"},
        422: {
            "model": ValidationErrorResponse,
            "description": "Pfad- oder Query-Validierung fehlgeschlagen",
        },
    },
)
async def get_entry(entry_id: int, session: Session = Depends(session_dep), user=Depends(get_current_user)):
    obj = session.get(EntryORM, entry_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "ENTRY_NOT_FOUND", "message": "Entry not found"}},
        )
    logging.getLogger("app.entries").debug("entry_retrieved", extra={"id": obj.id})
    return obj


@router.delete(
    "/{entry_id}",
    status_code=204,
    summary="Delete entry",
    description="Löscht einen Eintrag dauerhaft.",
    tags=["entries"],
    responses={
        204: {"description": "Erfolgreich gelöscht"},
        404: {"model": ErrorResponse, "description": "Eintrag nicht gefunden"},
    },
)
async def delete_entry(entry_id: int, session: Session = Depends(session_dep), user=Depends(get_current_user)):
    obj = session.get(EntryORM, entry_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "ENTRY_NOT_FOUND", "message": "Entry not found"}},
        )
    session.delete(obj)
    logging.getLogger("app.entries").info("entry_deleted", extra={"id": entry_id})
    # 204 No Content
    return None
