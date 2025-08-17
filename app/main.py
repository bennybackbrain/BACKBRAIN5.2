from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.core.logging_config import setup_logging
from app.middleware.request_id import RequestIDMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.database.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[override]
    # Startup
    setup_logging()
    logger = logging.getLogger("app.startup")
    logger.info("app_starting", extra={"version": "0.1.0"})
    init_db()
    logger.info("db_initialized")
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title="Backbrain5.2 API",
    version="0.1.0",
    description="API für Sammeln und Summarizing von Einträgen",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)

@app.get("/health", tags=["health"], summary="Health check", description="Returns application health status")
async def health():
    logging.getLogger("app.health").debug("health_check")
    return {"status": "ok"}

app.include_router(api_router, prefix="/api/v1")


# --- Standardisierte Fehlerbehandlung ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Wenn bereits unser Schema geliefert wurde, durchreichen
    body = exc.detail
    if isinstance(body, dict) and "error" in body:
        payload = body
    else:
        payload = {"error": {"code": f"HTTP_{exc.status_code}", "message": str(body)}}
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    issues = []
    for e in exc.errors():
        issues.append({
            "loc": list(e.get("loc", [])),
            "msg": e.get("msg", "Validation error"),
            "type": e.get("type", "validation_error"),
        })
    payload = {
        "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed"},
        "details": issues,
    }
    return JSONResponse(status_code=422, content=payload)

# Optional: Run with `uvicorn app.main:app --reload`
