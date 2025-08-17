"""Compatibility worker simulation for legacy tests.

Provides process_once() which executes pending or retry-eligible failed jobs
using the same process_job function.
"""
from datetime import datetime, UTC
from app.database.database import get_session
from app.database.models import JobORM, JobStatus
from app.services.job_processor import process_job
from app.core.config import settings


def process_once():  # pragma: no cover - helper for tests
    now = datetime.now(UTC)
    with get_session() as session:
        jobs = (
            session.query(JobORM)
            .filter(JobORM.status.in_([JobStatus.pending, JobStatus.failed]))
            .all()
        )
        ids: list[int] = []
        for j in jobs:
            if j.status == JobStatus.failed and j.retries > 0:
                elapsed = (now - j.updated_at).total_seconds()
                if elapsed < settings.job_retry_delay_seconds:
                    continue
            ids.append(j.id)
    for jid in ids:
        process_job(jid)
    return bool(ids)


def init_db():  # pragma: no cover
    from app.database.database import init_db as _i
    _i()
