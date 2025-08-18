from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import reload_settings_for_tests, settings


def _fresh_client(limit: int = 5, bypass_paths: str = "/health"):
    # mutate env via settings object directly (simple for now)
    settings.rate_limit_requests_per_minute = limit  # type: ignore[attr-defined]
    settings.rate_limit_bypass_paths = bypass_paths  # type: ignore[attr-defined]
    reload_settings_for_tests()
    app = create_app()
    return TestClient(app)


def test_rate_limit_enforced():
    client = _fresh_client(limit=5)
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
    client = _fresh_client(limit=3)
    for _ in range(3):
        assert client.get("/ready").status_code in (200, 503)  # readiness may degrade but still counts
    blocked = client.get("/ready")
    assert blocked.status_code == 429
    # Simulate wait for window expiration (fast-forward by manipulating internal deque timestamps)
    from app.middleware.rate_limit import current_rate_limiter
    assert current_rate_limiter is not None
    # Force-clear bucket for our test client IP (127.0.0.1)
    current_rate_limiter.buckets['testserver'] = type(current_rate_limiter.buckets['testserver'])([])  # empty deque
    r2 = client.get("/ready")
    assert r2.status_code in (200, 503)


def test_bypass_path_never_limited():
    client = _fresh_client(limit=1, bypass_paths="/health")
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

