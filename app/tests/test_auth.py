def test_auth_token_and_protected_flow(client, auth_headers, auth_token):
    # Unauthenticated request should fail
    r_unauth = client.get("/api/v1/entries/")
    assert r_unauth.status_code == 401
    # Token fixture already ensured user and token
    token = auth_token
    assert token
    r_create = client.post("/api/v1/entries/", json={"text": "Hello"}, headers=auth_headers)
    assert r_create.status_code == 202
    job_id = r_create.json()["job_id"]
    # Process job synchronously for test determinism
    from app.services.job_processor import process_job
    process_job(job_id)
    r_status = client.get(f"/api/v1/jobs/{job_id}/status", headers=auth_headers)
    assert r_status.status_code == 200
