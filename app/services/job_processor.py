import logging
from datetime import datetime, UTC
from threading import Timer
from app.database.database import get_session
from app.database.models import JobORM, JobStatus, EntryORM
from app.core.config import settings

logger = logging.getLogger("app.jobs")


def process_job(job_id: int) -> None:
    """Process a job with retry on failure.

    Failure simulation: if input_text contains the substring 'FAIL' (case-insensitive),
    an exception is raised to exercise the retry logic in tests.
    """
    with get_session() as session:
        job = session.get(JobORM, job_id)
        if not job:
            logger.warning("job_missing", extra={"job_id": job_id})
            return

        # Only pick up jobs that are pending or failed (for retry) and eligible for retry window
        if job.status not in (JobStatus.pending, JobStatus.failed):
            return

        # If previously failed, enforce backoff window
        if job.status == JobStatus.failed and job.retries > 0:
            elapsed = (datetime.now(UTC) - job.updated_at).total_seconds()
            if elapsed < settings.job_retry_delay_seconds:
                # Not yet time to retry
                return

        try:
            job.status = JobStatus.processing
            job.updated_at = datetime.now(UTC)
            session.flush()

            # Simulated failure trigger
            if "FAIL" in job.input_text.upper():
                raise RuntimeError("Simulated failure for testing")

            entry = EntryORM(text=job.input_text)
            session.add(entry)
            job.result_text = f"PROCESSED: {job.input_text[:50]}"
            job.status = JobStatus.completed
            job.updated_at = datetime.now(UTC)
            logger.info("job_completed", extra={"job_id": job.id})
        except Exception as exc:  # noqa: BLE001 broad for capturing processing failures
            job.retries += 1
            job.error_message = str(exc)[:500]
            # Decide if more retries are allowed
            if job.retries >= settings.job_max_retries:
                job.status = JobStatus.failed
                job.updated_at = datetime.now(UTC)
                logger.error(
                    "job_failed_final", extra={"job_id": job.id, "retries": job.retries, "error": job.error_message}
                )
            else:
                job.status = JobStatus.failed
                job.updated_at = datetime.now(UTC)
                logger.warning(
                    "job_failed_retrying", extra={"job_id": job.id, "retries": job.retries, "error": job.error_message}
                )
                # schedule next attempt after delay
                delay = settings.job_retry_delay_seconds
                Timer(delay, process_job, args=[job.id]).start()
