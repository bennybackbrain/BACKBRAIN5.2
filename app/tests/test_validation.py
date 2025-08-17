def test_create_entry_missing_field(client, auth_headers):
    r = client.post("/api/v1/entries/", json={}, headers=auth_headers)
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(issue["loc"][-1] == "text" for issue in body["details"])  # field missing


def test_entry_id_path_validation(client, auth_headers):
    r = client.get("/api/v1/entries/not-an-int", headers=auth_headers)
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any("entry_id" in issue["loc"] for issue in body["details"])  # entry_id invalid
