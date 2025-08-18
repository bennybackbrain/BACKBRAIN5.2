from __future__ import annotations
"""Rate limiting middleware.

Provides:
 - InMemoryRateLimiter (default for dev/testing)
 - RedisRateLimiter (if REDIS_URL configured) using INCR+EXPIRE per IP window.
"""
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import os
from app.core.config import settings
from app.core import metrics

try:  # optional dependency
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None  # type: ignore

current_rate_limiter: Optional['InMemoryRateLimiter'] = None


class InMemoryRateLimiter(BaseHTTPMiddleware):
    def __init__(self, app):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.window_seconds = 60
        self.max_requests = settings.rate_limit_requests_per_minute
        self.buckets: Dict[str, Deque[float]] = defaultdict(deque)
        global current_rate_limiter
        current_rate_limiter = self

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        # Build bypass set once (cache on instance)
        if not hasattr(self, '_bypass_set'):
            default_public = {"/read-file", "/read-file/", "/list-files", "/list-files/", "/write-file", "/write-file/", "/get_all_summaries", "/get_all_summaries/", "/version"}
            dynamic: set[str] = set()
            raw = settings.rate_limit_bypass_paths
            if raw:
                for p in raw.split(','):
                    p = p.strip()
                    if p:
                        dynamic.add(p if p.startswith('/') else '/' + p)
            self._bypass_set = default_public.union(dynamic)
        if path in self._bypass_set:
            response = await call_next(request)
            try:
                response.headers['X-RateLimit-Bypass'] = 'true'
            except Exception:
                pass
            return response
        # Determine key: API key id if strategy apikey and header present (later set by auth middleware), else IP
        key_basis = 'unknown'
        if settings.rate_limit_key_strategy == 'apikey' and hasattr(request.state, 'api_key_id'):
            key_basis = f"api_key:{getattr(request.state, 'api_key_id')}"
        else:
            key_basis = request.client.host if request.client else 'unknown'
        client_ip = key_basis
        now = time.time()
        dq = self.buckets[client_ip]
        while dq and now - dq[0] > self.window_seconds:
            dq.popleft()
        remaining = self.max_requests - len(dq)
        if remaining <= 0:
            try:
                metrics.rate_limit_drops_total.labels(path=path).inc()
            except Exception:
                pass
            resp = Response(status_code=429, content='Too Many Requests')
            resp.headers['X-RateLimit-Limit'] = str(self.max_requests)
            resp.headers['X-RateLimit-Remaining'] = '0'
            # Reset = seconds until current window ends (epoch seconds)
            window_end = int(now - (now % self.window_seconds) + self.window_seconds)
            resp.headers['X-RateLimit-Reset'] = str(window_end)
            # Compute dynamic retry-after (seconds until earliest event exits)
            retry_after = 60
            if dq:
                oldest_age = now - dq[0]
                retry_after = max(1, int(60 - oldest_age))
            resp.headers['Retry-After'] = str(retry_after)
            return resp
        dq.append(now)
    # counting now done in dedicated timing middleware; keep minimal compatibility
        response = await call_next(request)
        # Add headers (best-effort)
        try:
            response.headers['X-RateLimit-Limit'] = str(self.max_requests)
            used = len(dq)
            rem = max(0, self.max_requests - used)
            response.headers['X-RateLimit-Remaining'] = str(rem)
            window_end = int(now - (now % self.window_seconds) + self.window_seconds)
            response.headers['X-RateLimit-Reset'] = str(window_end)
            if path not in getattr(self, '_bypass_set', set()):
                response.headers['X-RateLimit-Bypass'] = 'false'
        except Exception:
            pass
        return response

class RedisRateLimiter(BaseHTTPMiddleware):  # pragma: no cover - requires redis runtime
    def __init__(self, app):  # type: ignore[no-untyped-def]
        super().__init__(app)
        if not settings.redis_url:
            raise RuntimeError("REDIS_URL not configured")
        if redis is None:
            raise RuntimeError("redis-py not installed; add 'redis' to requirements.txt")
        self.r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        self.window_seconds = 60
        self.max_requests = settings.rate_limit_requests_per_minute

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        client_ip = request.client.host if request.client else 'unknown'
        key = f"rl:{client_ip}:{int(time.time() // self.window_seconds)}"
        # Use pipeline for atomicity
        pipe = self.r.pipeline()
        pipe.incr(key, 1)
        pipe.expire(key, self.window_seconds)
        current, _ = pipe.execute()
        current_i = int(current)
        if current_i > self.max_requests:
            try:
                metrics.rate_limit_drops_total.labels(path=request.url.path).inc()
            except Exception:
                pass
            resp = Response(status_code=429, content='Too Many Requests')
            resp.headers['X-RateLimit-Limit'] = str(self.max_requests)
            resp.headers['X-RateLimit-Remaining'] = '0'
            resp.headers['Retry-After'] = '60'
            return resp
    # request counting handled centrally
        response = await call_next(request)
        try:
            response.headers['X-RateLimit-Limit'] = str(self.max_requests)
            rem = max(0, self.max_requests - current_i)
            response.headers['X-RateLimit-Remaining'] = str(rem)
        except Exception:  # pragma: no cover
            pass
        return response


def select_rate_limiter():  # returns class
    if os.getenv('BB_TESTING') == '1':  # disable limiting in test runs
        return NoOpRateLimiter
    if settings.redis_url:
        if redis is not None:
            return RedisRateLimiter
    return InMemoryRateLimiter


class NoOpRateLimiter(BaseHTTPMiddleware):  # pragma: no cover - trivial
    async def dispatch(self, request, call_next):  # type: ignore[no-untyped-def]
        return await call_next(request)

__all__ = ['InMemoryRateLimiter', 'RedisRateLimiter', 'select_rate_limiter', 'current_rate_limiter', 'NoOpRateLimiter']
