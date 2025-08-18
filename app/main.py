from __future__ import annotations

from fastapi import FastAPI, Request, HTTPException
import logging
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import router as v1_router
from app.api import public_alias
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.rate_limit import select_rate_limiter
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.request_metrics import RequestMetricsMiddleware
from app.middleware.api_key_auth import ApiKeyAuthMiddleware
from app.database.database import get_session
from sqlalchemy import text  # for readiness lightweight query
from app.services.webdav_client import load_webdav_config
import requests
from app.core import metrics
from typing import Any, Dict, List

from contextlib import asynccontextmanager
import pathlib

_VERSION_FILE = pathlib.Path(__file__).resolve().parent.parent / 'VERSION'
_SPEC_HASH_FILE = pathlib.Path(__file__).resolve().parent.parent / 'actions' / 'openapi-public.sha256'


@asynccontextmanager
async def lifespan(app: FastAPI):  # pragma: no cover
  try:
    logger.info("app_start", extra={"public_alias": settings.enable_public_alias})
  except Exception:
    pass
  yield
  # teardown placeholder

logger = logging.getLogger("startup")

def create_app() -> FastAPI:
  """Application factory to allow fresh instances in tests with mutated settings."""
  from app.core.config import settings as live_settings  # late import for updated values
  _app = FastAPI(title=live_settings.api_name, version="5.2-public-ok2", lifespan=lifespan)
  # --- Secret guard: prevent accidental use of production OpenAI keys locally ---
  # Heuristic: project (sk-proj-) or regular (sk-live, sk-prod) or long length >= 70
  key = live_settings.openai_api_key
  if key and not live_settings.confirm_use_prod_key:
    suspicious_prefixes = ("sk-proj-", "sk-live", "sk-prod", "sk-" )
    if any(key.startswith(p) for p in suspicious_prefixes) and len(key) > 40:
      raise RuntimeError("Refusing to start: OPENAI_API_KEY looks real. Set CONFIRM_USE_PROD_KEY=1 to allow.")
  # Override OpenAPI generation to inject a single servers list for GPT Action builder simplicity
  orig_openapi = _app.openapi
  def custom_openapi():  # type: ignore
    if _app.openapi_schema:
      return _app.openapi_schema
    schema = orig_openapi()
    # Inject exactly one server URL (Fly deployment) required by user spec
    schema['servers'] = [{"url": "https://backbrain5.fly.dev"}]
    # Keep schema minimal tolerant: do NOT enforce additionalProperties false anywhere here.
    _app.openapi_schema = schema
    return _app.openapi_schema
  _app.openapi = custom_openapi  # type: ignore
  # Middleware
  _app.add_middleware(RequestMetricsMiddleware)
  _app.add_middleware(RequestIDMiddleware)
  # Attach API key (non-blocking) before rate limiter so limiter can key by API key id
  _app.add_middleware(ApiKeyAuthMiddleware)
  RateLimiterCls = select_rate_limiter()
  _app.add_middleware(RateLimiterCls)
  # Structured access log after rate limiting (to log only accepted requests)
  if live_settings.access_log_enabled:
    try:
      _app.add_middleware(AccessLogMiddleware)
    except Exception:
      pass
  if live_settings.allowed_origins:
    origins = [o.strip() for o in live_settings.allowed_origins.split(',') if o.strip()]
  else:
    origins = ["*"]
  _app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
  )
  # Routers
  _app.include_router(v1_router.api_router, prefix="/api/v1")  # type: ignore[attr-defined]
  if live_settings.enable_public_alias:
    _app.include_router(public_alias.router)
  # Optional /diag
  if live_settings.enable_diag:
    @_app.api_route("/diag", methods=["GET", "POST"])
    async def diag(request: Request) -> JSONResponse:  # type: ignore
      body = None
      try:
        body = await request.json()  # type: ignore
      except Exception:
        try:
          body = (await request.body()).decode("utf-8")
        except Exception:
          body = None
      redacted_headers = {k: v for k, v in request.headers.items() if k.lower() not in {"authorization"}}
      return JSONResponse({"method": request.method, "path": request.url.path, "headers": redacted_headers, "body": body})
  # Exception handlers (need to be bound per app instance)
  from fastapi.exceptions import RequestValidationError as _RVE
  from fastapi import HTTPException as _HTTPExc
  from fastapi.responses import JSONResponse as _JR
  from typing import Any as _Any, Dict as _Dict, List as _List

  @_app.exception_handler(_RVE)  # type: ignore
  async def _validation_exception_handler(request: Request, exc: _RVE):  # type: ignore
    issues: _List[_Dict[str, _Any]] = []
    for e in exc.errors():
      issues.append({
        "loc": list(e.get("loc", [])),
        "msg": e.get("msg", "Validation error"),
        "type": e.get("type", "validation_error"),
      })
    payload: _Dict[str, _Any] = {
      "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed"},
      "details": issues,
    }
    return _JR(status_code=422, content=payload)

  @_app.exception_handler(Exception)  # type: ignore
  async def _unhandled_exception_handler(request: Request, exc: Exception):  # type: ignore
    msg = str(exc) if settings.debug else "Internal server error"
    return _JR(status_code=500, content={"error": {"code": "SERVER_ERROR", "message": msg}})

  @_app.exception_handler(_HTTPExc)  # type: ignore
  async def _http_exception_handler(request: Request, exc: _HTTPExc):  # type: ignore
    if isinstance(exc.detail, dict):
      return _JR(status_code=exc.status_code, content=exc.detail)
    return _JR(status_code=exc.status_code, content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}})
  return _app

# Default global app instance (backward compatibility)
app = create_app()

# Global machine/version identifiers (env overridable)
from os import getenv as _getenv  # localized import to avoid polluting top-level namespace
from typing import Callable, Awaitable
from starlette.responses import Response as StarletteResponse
MACHINE_ID = _getenv("FLY_MACHINE_ID", "unknown")
APP_VERSION = _getenv("APP_VERSION", "5.2-public-ok2")

@app.middleware("http")
async def add_ids(request: Request, call_next: Callable[[Request], Awaitable[StarletteResponse]]) -> StarletteResponse:  # pragma: no cover - trivial header injection
  resp = await call_next(request)
  try:  # defensive: never break pipeline due to header injection
    resp.headers["x-machine-id"] = MACHINE_ID
    resp.headers["x-app-version"] = APP_VERSION
  except Exception:
    pass
  return resp

@app.get("/health")
def health(request: Request) -> JSONResponse:  # enhanced public health
  payload = {"status": "ok", "version": APP_VERSION, "machine": MACHINE_ID}
  return JSONResponse(payload)

@app.get("/metrics")
def metrics_endpoint():  # Prometheus metrics
  text = metrics.render_prometheus()
  return PlainTextResponse(content=text, media_type="text/plain; version=0.0.4")

@app.get("/ready")
def ready() -> JSONResponse:  # lightweight readiness (DB + optional WebDAV)
  """Return 200 if core dependencies (DB) are available.

  WebDAV is treated as non-fatal: errors are surfaced in payload but won't block readiness.
  This prevents deploy flaps when external storage is temporarily unreachable.
  """
  db_status = "unknown"
  webdav_status = "skipped"
  issues: list[str] = []
  # DB check (SQLAlchemy 2.0 requires text())
  try:
    with get_session() as s:  # type: ignore[assignment]
      s.execute(text("SELECT 1"))  # type: ignore[arg-type]
    db_status = "ok"
  except Exception as exc:  # pragma: no cover
    db_status = "error"
    issues.append(f"db:{exc.__class__.__name__}")
  # WebDAV check only if config present
  try:
    base_url, user, pwd = load_webdav_config()
    if base_url and user and pwd:
      webdav_status = "ok"
      try:
        r = requests.request("PROPFIND", base_url.rstrip('/') + "/", auth=(user, pwd), headers={"Depth": "0"}, timeout=5)
        if r.status_code >= 400:
          webdav_status = f"http_{r.status_code}"
          issues.append(f"webdav:http_{r.status_code}")
      except Exception as exc:  # pragma: no cover
        webdav_status = "error"
        issues.append(f"webdav:{exc.__class__.__name__}")
  except Exception:
    # config missing -> keep skipped
    pass
  # Only fail readiness if DB is unavailable.
  overall = "ok" if db_status == "ok" else "degraded"
  status_code = 200 if overall == "ok" else 503
  return JSONResponse(status_code=status_code, content={
    "status": overall,
    "db": db_status,
    "webdav": webdav_status,
    "issues": issues,
  })

@app.get("/bb_version")
def bb_version() -> dict[str, object]:  # quick deployment verification route
  return {"app": settings.api_name, "public_alias": settings.enable_public_alias}

@app.get("/version")
def version_info() -> dict[str, str]:
  version = _VERSION_FILE.read_text().strip() if _VERSION_FILE.exists() else "unknown"
  spec_hash = _SPEC_HASH_FILE.read_text().strip() if _SPEC_HASH_FILE.exists() else "missing"
  return {"version": version, "specHash": spec_hash}

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):  # type: ignore[override]
  issues: List[Dict[str, Any]] = []
  for e in exc.errors():
    issues.append({
      "loc": list(e.get("loc", [])),
      "msg": e.get("msg", "Validation error"),
      "type": e.get("type", "validation_error"),
    })
  payload: Dict[str, Any] = {
    "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed"},
    "details": issues,
  }
  return JSONResponse(status_code=422, content=payload)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):  # type: ignore[override]
  # show detail only if debug enabled
  msg = str(exc) if settings.debug else "Internal server error"
  return JSONResponse(status_code=500, content={"error": {"code": "SERVER_ERROR", "message": msg}})

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[override]
  # Preserve existing structured detail if provided
  if isinstance(exc.detail, dict):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)
  return JSONResponse(status_code=exc.status_code, content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}})

__all__ = ["app"]

