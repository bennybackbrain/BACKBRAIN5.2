from __future__ import annotations

from sqlalchemy import Integer, String, DateTime, Enum as SAEnum
from datetime import datetime, UTC
import enum
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

class EntryORM(Base):
    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    text: Mapped[str] = mapped_column(String, nullable=False)


class JobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class JobType(str, enum.Enum):
    entry = "entry"
    file = "file"


class JobORM(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Store timezone-aware timestamps (UTC)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus), default=JobStatus.pending, nullable=False)
    input_text: Mapped[str] = mapped_column(String, nullable=False)
    result_text: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    job_type: Mapped[JobType] = mapped_column(SAEnum(JobType), default=JobType.entry, nullable=False)
    file_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


# Minimal file model for tracking uploaded files (public alias + summaries relation)
class FileORM(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String, nullable=True)


class SummaryORM(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    summary_text: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
