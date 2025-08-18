from fastapi.testclient import TestClient
from app.main import app
from app.middleware.rate_limit import InMemoryRateLimiter


def _get_limiter(client: TestClient) -> InMemoryRateLimiter:
    # Walk middleware stack to find limiter instance
    asgi = client.app
    # FastAPI app has attribute middleware_stack which builds on first request
    client.get("/health")  # trigger build
    stack = getattr(asgi, 'middleware_stack', None)
    depth = 0
    while stack is not None and depth < 10:
        depth += 1
        if isinstance(getattr(stack, 'app', None), InMemoryRateLimiter):
            return getattr(stack, 'app')  # type: ignore
        stack = getattr(stack, 'app', None)
    raise AssertionError("Rate limiter middleware not found")

def _ensure_limiter(client: TestClient, limit: int, bypass_health: bool = False):
    limiter = _get_limiter(client)
    limiter.max_requests = limit
    # Reset all buckets to ensure clean slate
    limiter.buckets.clear()
    # Ensure bypass for /health if requested
    if bypass_health:
        try:
            if not hasattr(limiter, '_bypass_set'):
                # Force build by one dispatch
                client.get("/bb_version")
            limiter._bypass_set.add('/health')  # type: ignore[attr-defined]
        except Exception:
            pass
    return limiter


def test_rate_limit_enforced():
    client = TestClient(app)
    _ensure_limiter(client, 5)
    ok_count = 0
    for _ in range(5):
        r = client.get("/bb_version")
        assert r.status_code == 200, f"Unexpected status before limit: {r.status_code}"
        ok_count += 1
    r = client.get("/bb_version")
    assert r.status_code == 429, f"Expected 429 after limit, got {r.status_code}"  # 6th should block
    assert r.headers.get("Retry-After") is not None
    assert r.headers.get("X-RateLimit-Limit") == "5"
    assert r.headers.get("X-RateLimit-Remaining") == "0"


def test_rate_limit_window_resets():
    client = TestClient(app)
    limiter = _ensure_limiter(client, 3)
    for _ in range(3):
        assert client.get("/ready").status_code in (200, 503)  # readiness may degrade but still counts
    blocked = client.get("/ready")
    assert blocked.status_code == 429
    # Simulate window reset by clearing bucket for client host key (testserver)
    limiter.buckets['testclient'].clear()
    r2 = client.get("/ready")
    assert r2.status_code in (200, 503)


def test_bypass_path_never_limited():
    client = TestClient(app)
    _ensure_limiter(client, 1, bypass_health=True)
    # Exceed limit many times on bypass path
    for _ in range(5):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.headers.get("X-RateLimit-Bypass") == "true"
    # Non-bypass should be limited after first
    r_norm1 = client.get("/bb_version")
    assert r_norm1.status_code == 200
    r_norm2 = client.get("/bb_version")
    assert r_norm2.status_code == 429

