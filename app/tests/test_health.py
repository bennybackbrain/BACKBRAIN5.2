from fastapi.testclient import TestClient
from app.main import app

def test_health():  # Updated health test
    client = TestClient(app)
    r = client.get("/health")  # health remains public
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
