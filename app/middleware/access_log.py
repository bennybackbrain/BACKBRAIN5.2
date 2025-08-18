from __future__ import annotations
import time
import json
from starlette.types import ASGIApp, Receive, Scope, Send, Message
from typing import Dict, Any

class AccessLogMiddleware:
    def __init__(self, app: ASGIApp, *, logger_name: str = "access"):
        self.app = app
        import logging
        self.logger = logging.getLogger(logger_name)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method")
        path = scope.get("path")
        start = time.time()
        status_holder: Dict[str, int] = {}

        async def send_wrapper(message: Message):
            if message.get("type") == "http.response.start":
                status_holder["status"] = int(message.get("status", 0))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start
            status = status_holder.get("status", 0)
            record: Dict[str, Any] = {
                "method": method,
                "path": path,
                "status": status,
                "duration_ms": round(duration * 1000, 3),
            }
            try:
                self.logger.info(json.dumps(record, separators=(",", ":")))
            except Exception:
                pass
