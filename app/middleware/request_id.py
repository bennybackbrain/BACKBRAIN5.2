import uuid
import contextvars
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)


def get_request_id() -> Optional[str]:
    return _request_id_ctx.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware, die pro Request eine UUID setzt und als Header zurückgibt."""

    def __init__(self, app, header_name: str = "X-Request-ID") -> None:  # type: ignore[override]
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rid = uuid.uuid4().hex
        token = _request_id_ctx.set(rid)
        request.state.request_id = rid
        try:
            response: Response = await call_next(request)
            response.headers[self.header_name] = rid
            return response
        finally:
            _request_id_ctx.reset(token)
