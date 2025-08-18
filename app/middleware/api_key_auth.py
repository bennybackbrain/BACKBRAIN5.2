from __future__ import annotations
"""API Key auth middleware (non-blocking).

If X-API-Key header present and valid, attaches request.state.api_key_id for downstream
rate limiter / handlers. Does NOT reject on invalid/missing key (public endpoints remain
accessible); explicit dependencies still enforce auth where needed.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.core.api_keys import verify_api_key
from app.database.database import get_session

class ApiKeyAuthMiddleware(BaseHTTPMiddleware):  # pragma: no cover
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        key = request.headers.get('X-API-Key')
        if key:
            try:
                with get_session() as s:  # type: ignore[assignment]
                    rec = verify_api_key(s, key)
                    if rec:
                        setattr(request.state, 'api_key_id', rec.id)
            except Exception:
                pass
        return await call_next(request)

__all__ = ["ApiKeyAuthMiddleware"]
