from worker_sim import process_once


def test_pagination_basic(client, auth_headers):
    for i in range(15):
        r = client.post("/api/v1/entries/", json={"text": f"Item {i}"}, headers=auth_headers)
        assert r.status_code == 202
        process_once()

    # page 1 (default limit 10)
    r1 = client.get("/api/v1/entries/", headers=auth_headers)
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["total"] == 15
    assert data1["limit"] == 10
    assert data1["offset"] == 0
    assert len(data1["items"]) == 10
    assert data1["items"][0]["text"] == "Item 0"

    # page 2
    r2 = client.get("/api/v1/entries/?offset=10&limit=10", headers=auth_headers)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["total"] == 15
    assert data2["limit"] == 10
    assert data2["offset"] == 10
    assert len(data2["items"]) == 5
    assert data2["items"][0]["text"] == "Item 10"

    # smaller page size
    r3 = client.get("/api/v1/entries/?limit=3", headers=auth_headers)
    assert r3.status_code == 200
    data3 = r3.json()
    assert data3["total"] == 15
    assert data3["limit"] == 3
    assert data3["offset"] == 0
    assert len(data3["items"]) == 3

    # limit upper bound (100) but only 15 total
    r4 = client.get("/api/v1/entries/?limit=100", headers=auth_headers)
    assert r4.status_code == 200
    data4 = r4.json()
    assert data4["limit"] == 100
    assert len(data4["items"]) == 15

    # offset beyond total -> empty items
    r5 = client.get("/api/v1/entries/?offset=999", headers=auth_headers)
    assert r5.status_code == 200
    data5 = r5.json()
    assert data5["items"] == []

    # invalid limit (0) -> 422
    r6 = client.get("/api/v1/entries/?limit=0", headers=auth_headers)
    assert r6.status_code == 422
    j6 = r6.json()
    assert j6["error"]["code"] == "VALIDATION_ERROR"

    # invalid offset (-1) -> 422
    r7 = client.get("/api/v1/entries/?offset=-1", headers=auth_headers)
    assert r7.status_code == 422
    j7 = r7.json()
    assert j7["error"]["code"] == "VALIDATION_ERROR"
