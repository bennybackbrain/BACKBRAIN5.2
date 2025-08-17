from fastapi.testclient import TestClient
from app.main import app


def test_request_id_header(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("BB_DB_URL", f"sqlite:///{db_file}")
    import app.database.database as db
    db.init_db()

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    rid = r.headers.get("X-Request-ID")
    assert rid is not None
    assert len(rid) == 32  # uuid4 hex
