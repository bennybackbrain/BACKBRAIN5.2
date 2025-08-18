
from fastapi.testclient import TestClient
from app.main import create_app


def test_query_endpoint():
    # Schreibe Testdaten in den Cache
    import os
    cache_dir = "test_cache_summaries"
    os.makedirs(cache_dir, exist_ok=True)
    os.environ["SUMMARY_CACHE_ENABLED"] = "true"
    os.environ["SUMMARY_CACHE_DIR"] = cache_dir
    with open(f"{cache_dir}/test1.summary.md", "w") as f:
        f.write("Wetter 2025 und Bank 2024: Test-Notiz.")
    payload = {"query": "Wetter 2025 und Bankauszug 2024?", "top_k": 1}
    client = TestClient(create_app())
    response = client.post("/api/v1/query", json=payload, headers={"X-API-Key": "test"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert data["sources"]
