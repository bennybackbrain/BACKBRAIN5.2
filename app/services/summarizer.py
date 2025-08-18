from __future__ import annotations
"""Summarizer abstraction layer.

Phase 1: simple heuristic fallback summarizer.
Later: OpenAI / local model adapters.
"""
from dataclasses import dataclass
import hashlib
import time
from typing import Dict, Tuple, Any
import logging
import httpx
from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.database.models import SummarizerUsageORM

from app.core.config import settings, get_summary_cache_enabled, get_summary_cache_dir
from app.services.webdav_client import write_file_content, get_file_content
import os

def _atomic_write(path: str, content: str):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)

def write_summary_dual(stem: str, content: str):
    """Write summary to Nextcloud (source of truth) and to local cache."""
    # Nextcloud-Write
    nc_path = f"BACKBRAIN5.2/summaries/{stem}.summary.md"
    write_file_content(nc_path, content)
    # Cache-Write
    if get_summary_cache_enabled():
        try:
            fname = f"{stem}.summary.md"
            cache_path = os.path.join(get_summary_cache_dir(), fname)
            _atomic_write(cache_path, content)
            try:
                from app.core import metrics
                metrics.inc_labeled("bb_summary_cache_write_total", status="ok")
            except Exception:
                pass
        except Exception as e:
            logging.getLogger("app.summarizer").warning(f"cache_write_failed for {stem}: {e}")
            try:
                from app.core import metrics
                metrics.inc_labeled("bb_summary_cache_write_total", status="fail")
            except Exception:
                pass

def read_summary_preferring_cache(stem: str) -> str | None:
    fname = f"{stem}.summary.md"
    if get_summary_cache_enabled():
        p = os.path.join(get_summary_cache_dir(), fname)
        try:
            with open(p, "r", encoding="utf-8") as f:
                try:
                    from app.core import metrics
                    metrics.inc_labeled("bb_summary_cache_read_total", source="cache")
                except Exception:
                    pass
                return f.read()
        except FileNotFoundError:
            pass
    # Fallback: Nextcloud
    nc_path = f"BACKBRAIN5.2/summaries/{stem}.summary.md"
    try:
        from app.core import metrics
        metrics.inc_labeled("bb_summary_cache_read_total", source="nextcloud")
    except Exception:
        pass
    return get_file_content(nc_path)

def _atomic_write(path: str, content: str):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)

def write_summary_dual(stem: str, content: str):
    """Write summary to Nextcloud (source of truth) and to local cache."""
    # Nextcloud-Write
    nc_path = f"BACKBRAIN5.2/summaries/{stem}.summary.md"
    write_file_content(nc_path, content)
    # Cache-Write
    if get_summary_cache_enabled():
        try:
            fname = f"{stem}.summary.md"
            cache_path = os.path.join(get_summary_cache_dir(), fname)
            _atomic_write(cache_path, content)
            try:
                from app.core import metrics
                metrics.inc_labeled("bb_summary_cache_write_total", status="ok")
            except Exception:
                pass
        except Exception as e:
            logging.getLogger("app.summarizer").warning(f"cache_write_failed for {stem}: {e}")
            try:
                from app.core import metrics
                metrics.inc_labeled("bb_summary_cache_write_total", status="fail")
            except Exception:
                pass
                from app.core import metrics
                metrics.inc("bb_summary_cache_write_total", labels={"status": "fail"})
            except Exception:
                pass

def read_summary_preferring_cache(stem: str) -> str | None:
    fname = f"{stem}.summary.md"
    if get_summary_cache_enabled():
        p = os.path.join(get_summary_cache_dir(), fname)
        try:
            with open(p, "r", encoding="utf-8") as f:
                try:
                    from app.core import metrics
                    metrics.inc("bb_summary_cache_read_total", labels={"source": "cache"})
                except Exception:
                    pass
                return f.read()
        except FileNotFoundError:
            pass
    # Fallback: Nextcloud
    try:
        from app.core import metrics
        metrics.inc("bb_summary_cache_read_total", labels={"source": "nextcloud"})
    except Exception:
        pass
    nc_path = f"BACKBRAIN5.2/summaries/{stem}.summary.md"
    return get_file_content(nc_path)

logger = logging.getLogger("app.summarizer")

@dataclass
class SummaryResult:
    model: str
    summary: str


_cache: Dict[str, Tuple[float, SummaryResult]] = {}
_CACHE_TTL = 3600.0  # seconds
_RETRY_DELAYS = [0.5, 1.0, 2.0]

def _heuristic(content: str) -> SummaryResult:
    if not content:
        return SummaryResult(model="heuristic", summary="(empty)")
    words = content.strip().split()
    short = " ".join(words[:64])
    if len(short) > 500:
        short = short[:497] + "..."
    return SummaryResult(model="heuristic", summary=short)


def _record_usage(**kw: Any) -> None:
    session: Session | None = None
    try:
        session = SessionLocal()
        session.add(SummarizerUsageORM(**kw))
        session.commit()
    except Exception as exc:  # pragma: no cover
        logger.debug("summarizer_usage_record_failed", extra={"error": str(exc)})
    finally:  # pragma: no cover
        if session is not None:
            try:
                session.close()
            except Exception:
                pass


def _openai_call(content: str) -> SummaryResult:
    """Call OpenAI (or compatible) chat completion API to summarize content.

    Fallback: heuristic summarizer on any error or missing key.
    Uses a short system+user prompt. Truncates input to a safety max.
    """
    if not settings.openai_api_key:
        logger.debug("openai_missing_key_fallback")
        return _heuristic(content)
    base = settings.openai_base_url or "https://api.openai.com/v1"
    url = base.rstrip('/') + "/chat/completions"
    model = settings.summary_model
    # Hard cap input size (tokens rough proxy) to avoid huge payloads
    if len(content) > 16000:
        content_slice = content[:16000]
    else:
        content_slice = content
    prompt = (
        "Erstelle eine prägnante Zusammenfassung (max ~180 Wörter). "
        "Fokussiere auf Kernaussagen, Daten, Beträge, Hashtags. "
        "Antworte in deutscher Sprache."
    )
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Du bist ein hilfreicher, präziser Zusammenfasser."},
            {"role": "user", "content": f"{prompt}\n\nTEXT BEGINN:\n{content_slice}\nTEXT ENDE"},
        ],
        "temperature": 0.2,
        "max_tokens": 400,
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    last_err: Exception | None = None
    for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
        try:
            t0 = time.time()
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, headers=headers, json=body)
            dt_ms = int((time.time() - t0) * 1000)
            if resp.status_code != 200:
                last_err = Exception(f"status {resp.status_code} body={resp.text[:200]}")
                logger.warning("openai_non_200", extra={"status": resp.status_code, "attempt": attempt})
            else:
                data: dict[str, Any] = resp.json()  # type: ignore[assignment]
                raw_choices = data.get("choices") or [{}]
                if isinstance(raw_choices, list) and raw_choices:
                    choice: dict[str, Any] | Any = raw_choices[0]
                else:
                    choice = {}
                msg: str | None = choice.get("message", {}).get("content") if isinstance(choice, dict) else None
                usage: dict[str, Any] = data.get("usage") or {}
                if not msg:
                    last_err = Exception("empty_message")
                    logger.warning("openai_empty_message", extra={"attempt": attempt})
                else:
                    summary = str(msg).strip()
                    if len(summary) > 4000:
                        summary = summary[:3997] + "..."
                    meta = {
                        "model": model,
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "total_tokens": usage.get("total_tokens"),
                        "duration_ms": dt_ms,
                        "attempt": attempt,
                    }
                    logger.info("summarizer_done", extra=meta)
                    # persist (source and file/prefix filled by caller via context var? simple: only model+tokens here)
                    _record_usage(model=model,
                                  prompt_tokens=meta["prompt_tokens"],
                                  completion_tokens=meta["completion_tokens"],
                                  total_tokens=meta["total_tokens"],
                                  duration_ms=meta["duration_ms"],
                                  source=None,
                                  file_name=None,
                                  prefix=None,
                                  fallback=0)
                    return SummaryResult(model=model, summary=summary)
        except Exception as exc:  # pragma: no cover
            last_err = exc
            logger.warning("openai_call_attempt_failed", extra={"error": str(exc), "attempt": attempt})
        time.sleep(delay)
    logger.error("openai_call_failed_all", extra={"error": str(last_err) if last_err else None})
    # fallback path
    h = _heuristic(content)
    _record_usage(model=h.model, prompt_tokens=None, completion_tokens=None, total_tokens=None, duration_ms=None, source=None, file_name=None, prefix=None, fallback=1)
    return h


def summarize_text(content: str, model: str | None = None, *, source: str | None = None, file_name: str | None = None, prefix: str | None = None) -> SummaryResult:
    provider = settings.summarizer_provider
    # Provider switch logic: any value != 'openai' falls back to heuristic (recorded as fallback=1)
    chosen_model = model or settings.summary_model
    cache_key = hashlib.sha256((provider + "::" + chosen_model + "::" + content[:5000]).encode()).hexdigest()
    now = time.time()
    cached = _cache.get(cache_key)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]
    if provider == "openai":
        res = _openai_call(content)
        if res.model == "heuristic":  # indicates fallback
            res = SummaryResult(model=res.model, summary=res.summary + "\n\n(fallback: heuristic)")
            # already recorded as fallback inside _openai_call
        else:
            # augment last row with context if provided (best-effort update)
            if source or file_name or prefix:
                session: Session | None = None
                try:
                    session = SessionLocal()
                    last = session.query(SummarizerUsageORM).order_by(SummarizerUsageORM.id.desc()).first()
                    if last and last.source is None and last.file_name is None and last.prefix is None:
                        last.source = source
                        last.file_name = file_name
                        last.prefix = prefix
                        session.commit()
                except Exception as exc:  # pragma: no cover
                    logger.debug("summarizer_usage_context_update_failed", extra={"error": str(exc)})
                finally:  # pragma: no cover
                    if session is not None:
                        try:
                            session.close()
                        except Exception:
                            pass
    else:
        t0 = time.time()
        res = _heuristic(content)
        _record_usage(model=res.model, prompt_tokens=None, completion_tokens=None, total_tokens=None, duration_ms=int((time.time()-t0)*1000), source=source, file_name=file_name, prefix=prefix, fallback=1)
    _cache[cache_key] = (now, res)
    return res
