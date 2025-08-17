from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app.database.database import get_session
from app.database.models import JobORM, JobStatus
from app.core.security import get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])

def session_dep():
    with get_session() as s:
        yield s

class JobStatusOut(BaseModel):
    job_id: int
    status: JobStatus
    result_text: str | None = None
    error_message: str | None = None
    retries: int | None = None

    model_config = ConfigDict(json_schema_extra={"example": {"job_id": 1, "status": "completed", "result_text": "SUMMARY ..."}})

@router.get("/{job_id}/status", response_model=JobStatusOut, summary="Get job status")
async def get_job_status(job_id: int, session: Session = Depends(session_dep), user=Depends(get_current_user)):
    job = session.get(JobORM, job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Job not found"}})
    return {
        "job_id": job.id,
        "status": job.status,
        "result_text": job.result_text,
        # Only expose error information if final failure (no more retries)
        "error_message": job.error_message if job.status == JobStatus.failed else None,
        "retries": job.retries,
    }
