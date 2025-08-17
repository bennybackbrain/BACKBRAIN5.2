def test_get_not_found(client, auth_headers):
    r = client.get("/api/v1/entries/9999", headers=auth_headers)
    assert r.status_code == 404
    data = r.json()
    assert data["error"]["code"] == "ENTRY_NOT_FOUND"


def test_delete(client, auth_headers):
    # Create job to create entry asynchronously
    r = client.post("/api/v1/entries/", json={"text": "Delete me"}, headers=auth_headers)
    assert r.status_code == 202
    # We don't have direct job completion sync; simulate processing by invoking processor directly
    # Import here to avoid circular
    from app.services.job_processor import process_job
    job_id = r.json()["job_id"]
    process_job(job_id)
    # Entry should now exist with id 1
    entry_id = 1
    r2 = client.delete(f"/api/v1/entries/{entry_id}", headers=auth_headers)
    assert r2.status_code == 204
    r3 = client.get(f"/api/v1/entries/{entry_id}", headers=auth_headers)
    assert r3.status_code == 404
