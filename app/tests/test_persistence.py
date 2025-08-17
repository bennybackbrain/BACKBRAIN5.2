from worker_sim import process_once


def test_create_and_persist_entry(client, auth_headers):
    resp = client.post("/api/v1/entries/", json={"text": "Persist me"}, headers=auth_headers)
    assert resp.status_code == 202
    process_once()
    resp2 = client.get("/api/v1/entries/1", headers=auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["text"] == "Persist me"
