import re
from fastapi.testclient import TestClient

from app.main import app


def test_metrics_endpoint_basic():  # type: ignore[no-untyped-def]
    client = TestClient(app)

    # Generate some traffic (metrics middleware should record these)
    for _ in range(3):
        hr = client.get("/health")
        assert hr.status_code == 200

    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text

    # Core counter present
    assert "http_requests_total" in body
    # Histogram buckets present
    assert "http_request_duration_seconds_bucket" in body

    # Specific labeled counter for /health with status 200 exists and >= 3
    m = re.search(r'http_requests_total\{[^}]*path="/health"[^}]*status="200"[^}]*} (\d+)', body)
    assert m, "Expected labeled http_requests_total for /health status=200"
    assert int(m.group(1)) >= 3

    # rate_limit_drops_total may be zero; just ensure metric name appears once traffic grows (non-fatal if absent)
    # (Do not assert its presence to avoid flakiness.)
