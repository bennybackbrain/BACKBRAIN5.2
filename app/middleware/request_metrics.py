from __future__ import annotations
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.metrics import http_requests_total, http_request_duration_seconds

class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Collect per-request Prometheus metrics.

    Records:
      - http_requests_total{method,path,status}
      - http_request_duration_seconds histogram
    Excludes /metrics to avoid self-scrape noise.
    """
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        if path == '/metrics':
            return await call_next(request)
        method = request.method
        start = time.time()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            dur = time.time() - start
            label_path = path if len(path) < 100 else path[:97] + '...'
            try:
                http_requests_total.labels(method=method, path=label_path, status=str(status_code)).inc()
                http_request_duration_seconds.labels(method=method, path=label_path).observe(dur)
            except Exception:
                pass

__all__ = ["RequestMetricsMiddleware"]
