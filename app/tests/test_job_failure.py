import time


def test_job_failure_and_error_reporting(client, auth_headers, monkeypatch):
    monkeypatch.setenv("JOB_MAX_RETRIES", "1")
    monkeypatch.setenv("JOB_RETRY_DELAY_SECONDS", "1")
    r = client.post("/api/v1/entries/", json={"text": "This will FAIL"}, headers=auth_headers)
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    deadline = time.time() + 5
    error_message = None
    while time.time() < deadline:
        s = client.get(f"/api/v1/jobs/{job_id}/status", headers=auth_headers)
        data = s.json()
        if data["status"] == "failed":
            error_message = data.get("error_message")
            break
        time.sleep(0.1)
    assert error_message is not None and "Simulated failure" in error_message
