from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, cast
from app.core.security import get_current_user, UserORM
from app.services.webdav_client import get_file_content, write_file_content
from app.core.config import settings
from app.services.summarizer import summarize_text
from app.database.database import get_session
from app.database.models import SummarizerUsageORM
from sqlalchemy import func
import os
import re

router = APIRouter(prefix="/summarizer", tags=["summarizer"])

class SummarizeIn(BaseModel):
    kind: str = Field(..., pattern="^(entries|summaries)$")
    name: str
    style: str | None = Field(None, pattern="^(short|bullet|long)?$")

class SummarizeOut(BaseModel):
    summary_path: str
    tags: List[str]
    chars_in: int
    chars_out: int
    model: str

class SummarizePrefixIn(BaseModel):
    kind: str = Field(..., pattern="^(entries|summaries)$")
    prefix: str
    limit: int = 50
    style: str | None = Field(None, pattern="^(short|bullet|long)?$")

class SummarizePrefixOut(BaseModel):
    processed: int
    files: List[str]
    bundle_summary_path: str
    model: str


class SummarizerUsageItem(BaseModel):
    id: int
    created_at: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    duration_ms: int | None
    source: str | None
    file_name: str | None
    prefix: str | None
    fallback: bool


class SummarizerUsageStats(BaseModel):
    total_rows: int
    fallback_rows: int
    fallback_rate: float | None
    total_prompt_tokens: int | None
    total_completion_tokens: int | None
    total_total_tokens: int | None
    by_model: Dict[str, Dict[str, int | float | None]]


class SummarizerUsageResponse(BaseModel):
    items: List[SummarizerUsageItem]
    stats: SummarizerUsageStats

_MAX_CHARS_DIRECT = 30_000
_CHUNK_SIZE = 4_000
_CHUNK_OVERLAP = 250  # weicher Übergang zwischen Chunks

_DEF_BULLET_JOIN = "\n\n"

_TAG_PATTERN = re.compile(r"#\w{3,32}")
_DATE_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_AMOUNT_PATTERN = re.compile(r"\b(\d+[.,]\d{2})\b")


def _extract_tags(text: str) -> list[str]:
    tags: set[str] = set()
    for pat in (_TAG_PATTERN, _DATE_PATTERN, _AMOUNT_PATTERN):
        for m in pat.findall(text):
            # normalize
            tag = m
            if pat is _AMOUNT_PATTERN:
                tag = f"amount:{m.replace(',', '.')}"
            tags.add(tag)
    # limit number of tags
    out: list[str] = sorted(tags)
    return out[:15]


def _chunk(text: str, size: int, overlap: int) -> list[str]:
    if size <= 0:
        return [text]
    if overlap < 0:
        overlap = 0
    if overlap >= size:
        overlap = size // 4  # safeguard
    step = size - overlap
    parts: list[str] = []
    i = 0
    while i < len(text):
        parts.append(text[i:i+size])
        i += step
    return parts


@router.post("/summarize-file", response_model=SummarizeOut, summary="Summarize a file and store summary")
async def summarize_file(body: SummarizeIn, user: UserORM = Depends(get_current_user)) -> SummarizeOut:
    if body.kind not in ("entries", "summaries"):
        raise HTTPException(status_code=400, detail={"error": {"code": "UNSUPPORTED_KIND", "message": "kind must be entries|summaries"}})
    # Map kind to directory
    base_dir = settings.inbox_dir if body.kind == "entries" else settings.summaries_dir
    rel_path = f"{base_dir}/{body.name}".replace('..','_').lstrip('/')
    try:
        content = get_file_content(rel_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": {"code": "FILE_NOT_FOUND", "message": body.name}})
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail={"error": {"code": "READ_FAILED", "message": str(exc)}})

    chars_in = len(content)
    style = body.style or "short"

    if chars_in <= _MAX_CHARS_DIRECT:
        summary_res = summarize_text(content, model=None, source="single", file_name=body.name)
        summary_text = summary_res.summary
        used_model = summary_res.model
    else:
        parts = _chunk(content, _CHUNK_SIZE, _CHUNK_OVERLAP)
        partials: list[str] = []
        used_model = None
        for p in parts:
            r = summarize_text(p, model=None, source="single-chunk", file_name=body.name)
            partials.append(r.summary)
            used_model = used_model or r.model
        joined = _DEF_BULLET_JOIN.join(partials)
        # compress joined again
        summary_res = summarize_text(joined, model=None, source="single-join", file_name=body.name)
        summary_text = summary_res.summary
        used_model = used_model or summary_res.model

    if style == "bullet":
        # naive bullet formatting
        summary_text = "\n".join(f"- {line.strip()}" for line in re.split(r"[\n\.]+", summary_text) if line.strip())
    elif style == "long":
        # attempt to re-expand (placeholder: just reuse for now)
        if len(summary_text) < 300 and chars_in > 800:
            # try a second pass to lengthen
            summary_text = summarize_text(content[:8000], model=None, source="single-long", file_name=body.name).summary

    tags = _extract_tags(content + "\n" + summary_text)

    # Write summary file under summaries
    stem = os.path.splitext(os.path.basename(body.name))[0]
    summary_filename = f"{stem}.summary.md"
    summary_rel = f"{settings.summaries_dir}/{summary_filename}".lstrip('/')
    try:
        write_file_content(summary_rel, summary_text)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail={"error": {"code": "WRITE_FAILED", "message": str(exc)}})

    return SummarizeOut(summary_path=summary_rel, tags=tags, chars_in=chars_in, chars_out=len(summary_text), model=used_model or "heuristic")


@router.post("/summarize-prefix", response_model=SummarizePrefixOut, summary="Summarize multiple files by prefix and create bundle summary")
async def summarize_prefix(body: SummarizePrefixIn, user: UserORM = Depends(get_current_user)) -> SummarizePrefixOut:
    if body.kind not in ("entries", "summaries"):
        raise HTTPException(status_code=400, detail={"error": {"code": "UNSUPPORTED_KIND", "message": "kind must be entries|summaries"}})
    # list matching files via list-files endpoint logic (reuse DB-less approach: scan directory?) – we have storage on WebDAV; simpler: use local summaries dir if kind==summaries else inbox
    base_dir = settings.inbox_dir if body.kind == "entries" else settings.summaries_dir
    # Collect candidates from filesystem (assuming local mirror); fallback: return error if directory missing
    dir_path = base_dir
    try:
        from os import listdir
        candidates = [f for f in listdir(dir_path) if f.startswith(body.prefix)]
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": {"code": "LIST_FAILED", "message": str(exc)}})
    candidates = sorted(candidates)[: max(1, min(body.limit, 500))]
    processed_files: list[str] = []
    partial_summaries: list[str] = []
    used_model: str | None = None
    for fname in candidates:
        rel = f"{base_dir}/{fname}".lstrip('/')
        try:
            content = get_file_content(rel)
        except Exception:
            continue
        r = summarize_text(content, model=None, source="prefix-part", file_name=fname, prefix=body.prefix)
        partial_summaries.append(f"# {fname}\n\n{r.summary}\n")
        used_model = used_model or r.model
        processed_files.append(fname)
    if not partial_summaries:
        raise HTTPException(status_code=404, detail={"error": {"code": "NO_MATCHING_FILES", "message": body.prefix}})
    bundle_joined = "\n\n".join(partial_summaries)
    # Second pass compress
    bundle_res = summarize_text(bundle_joined[:60_000], model=None, source="prefix-bundle", prefix=body.prefix)
    bundle_summary = bundle_res.summary
    model_final = used_model or bundle_res.model
    # store bundle summary
    safe_prefix = body.prefix.replace('/', '_')
    bundle_name = f"{safe_prefix}.bundle.summary.md"
    bundle_rel = f"{settings.summaries_dir}/{bundle_name}".lstrip('/')
    try:
        write_file_content(bundle_rel, bundle_summary)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error": {"code": "WRITE_FAILED", "message": str(exc)}})
    return SummarizePrefixOut(processed=len(processed_files), files=processed_files, bundle_summary_path=bundle_rel, model=model_final)


@router.get("/usage", response_model=SummarizerUsageResponse, summary="Recent summarizer usage + stats")
async def summarizer_usage(limit: int = 100) -> SummarizerUsageResponse:
    limit = max(1, min(limit, 1000))
    with get_session() as session:  # type: ignore[assignment]
        q = session.query(SummarizerUsageORM).order_by(SummarizerUsageORM.id.desc()).limit(limit)
        rows = list(q)  # type: ignore[var-annotated]
        # overall stats (not limited) — can be expensive on huge tables; acceptable here
        total_rows = session.query(func.count(SummarizerUsageORM.id)).scalar() or 0
        fallback_rows = session.query(func.count(SummarizerUsageORM.id)).filter(SummarizerUsageORM.fallback == 1).scalar() or 0
        sum_prompt = session.query(func.sum(SummarizerUsageORM.prompt_tokens)).scalar()
        sum_completion = session.query(func.sum(SummarizerUsageORM.completion_tokens)).scalar()
        sum_total = session.query(func.sum(SummarizerUsageORM.total_tokens)).scalar()
        by_model_rows = session.query(
            SummarizerUsageORM.model,
            func.count(SummarizerUsageORM.id),
            func.sum(SummarizerUsageORM.total_tokens),
            func.sum(SummarizerUsageORM.prompt_tokens),
            func.sum(SummarizerUsageORM.completion_tokens),
            func.sum(SummarizerUsageORM.fallback),
        ).group_by(SummarizerUsageORM.model).all()
    items: List[SummarizerUsageItem] = []
    for r in rows:
        items.append(SummarizerUsageItem(
            id=r.id,
            created_at=r.created_at.isoformat(),
            model=r.model,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            total_tokens=r.total_tokens,
            duration_ms=r.duration_ms,
            source=r.source,
            file_name=r.file_name,
            prefix=r.prefix,
            fallback=bool(r.fallback),
        ))
    by_model: Dict[str, Dict[str, int | float | None]] = {}
    for model_name, cnt, sum_tot, sum_pr, sum_co, sum_fb in by_model_rows:
        by_model[str(model_name)] = {
            "count": int(cnt or 0),
            "total_tokens": int(sum_tot or 0) if sum_tot is not None else None,
            "prompt_tokens": int(sum_pr or 0) if sum_pr is not None else None,
            "completion_tokens": int(sum_co or 0) if sum_co is not None else None,
            "fallbacks": int(sum_fb or 0),
            "fallback_rate": (float(sum_fb)/float(cnt)) if cnt else None,
        }
    stats = SummarizerUsageStats(
        total_rows=total_rows,
        fallback_rows=fallback_rows,
        fallback_rate=(fallback_rows/total_rows) if total_rows else None,
        total_prompt_tokens=int(sum_prompt or 0) if sum_prompt is not None else None,
        total_completion_tokens=int(sum_completion or 0) if sum_completion is not None else None,
        total_total_tokens=int(sum_total or 0) if sum_total is not None else None,
        by_model=by_model,
    )
    return SummarizerUsageResponse(items=items, stats=stats)
