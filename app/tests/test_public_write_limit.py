import os
import pytest
from fastapi.testclient import TestClient
import app.core.config as cfg
from app.main import create_app

@pytest.fixture()
def public_client(tmp_path):  # type: ignore[no-untyped-def]
    os.environ["BB_DB_URL"] = f"sqlite:///{tmp_path / 'pub.db'}"
    os.environ["ENABLE_PUBLIC_ALIAS"] = "true"
    os.environ["PUBLIC_WRITEFILE_LIMIT_PER_MINUTE"] = "3"  # low for test
    cfg.reload_settings_for_tests()
    test_app = create_app()
    return TestClient(test_app)

def test_public_write_limit(public_client: TestClient):
    # Perform 3 writes (should pass)
    for i in range(3):
        r = public_client.post("/write-file", json={"name": "same.txt", "kind": "entries", "content": f"hi {i}"})
        assert r.status_code == 200, r.text
        if i == 0:
            assert r.headers.get('X-Public-Write-Limit') == '3'
    # 4th within same minute should 429
    r = public_client.post("/write-file", json={"name": "same.txt", "kind": "entries", "content": "hi 3"})
    assert r.status_code == 429, r.text
    assert 'limit' in r.text.lower(), r.text
