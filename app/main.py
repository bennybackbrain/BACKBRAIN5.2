from __future__ import annotations

from fastapi import FastAPI, Request, HTTPException
import logging
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import router as v1_router
from app.api import public_alias
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.rate_limit import select_rate_limiter
from app.database.database import get_session
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
  _app = FastAPI(title=live_settings.api_name, version="0.1.0", lifespan=lifespan)
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
  _app.add_middleware(RequestIDMiddleware)
  RateLimiterCls = select_rate_limiter()
  _app.add_middleware(RateLimiterCls)
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
  return _app

# Default global app instance (backward compatibility)
app = create_app()

@app.get("/health")
def health() -> dict[str, str]:  # simple public health
  return {"status": "ok"}

@app.get("/metrics")
def metrics_endpoint():  # Prometheus metrics
  text = metrics.render_prometheus()
  return JSONResponse(content=text, media_type="text/plain")

@app.get("/ready")
def ready() -> JSONResponse:  # lightweight readiness (DB + optional WebDAV)
  db_status = "unknown"
  webdav_status = "skipped"
  issues: list[str] = []
  # DB check
  try:
    with get_session() as s:  # type: ignore[assignment]
      s.execute("SELECT 1")  # type: ignore[arg-type]
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
        # HEAD (fast); some servers may not allow HEAD -> fallback GET with depth header minimal
        r = requests.request("PROPFIND", base_url.rstrip('/') + "/", auth=(user, pwd), headers={"Depth":"0"}, timeout=5)
        if r.status_code >= 400:
          webdav_status = f"http_{r.status_code}"
          issues.append(f"webdav:http_{r.status_code}")
      except Exception as exc:  # pragma: no cover
        webdav_status = "error"
        issues.append(f"webdav:{exc.__class__.__name__}")
  except Exception:
    # config missing -> keep skipped
    pass
  overall = "ok" if db_status == "ok" and (webdav_status in {"ok", "skipped"}) else "degraded"
  status_code = 200 if overall == "ok" else 503
  counters, _gauges = metrics.snapshot()
  expose = {k: v for k, v in counters.items() if k in {
    'public_writefile_requests_total', 'public_writefile_limited_total', 'rate_limit_drops_total'
  }}
  return JSONResponse(status_code=status_code, content={
    "status": overall,
    "db": db_status,
    "webdav": webdav_status,
    "issues": issues,
    "counters": expose,
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

