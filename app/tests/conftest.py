import os
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.database.database import get_session, init_db
from app.database.models import UserORM
from app.core.security import hash_password


@pytest.fixture()
def client(tmp_path):
    # Fresh isolated DB per test
    os.environ["BB_DB_URL"] = f"sqlite:///{tmp_path / 'test.db'}"
    os.environ["BB_TESTING"] = "1"
    os.environ['ENABLE_PUBLIC_ALIAS'] = '0'  # keep OpenAPI stable relative to frozen spec
    init_db()
    test_app = create_app()
    return TestClient(test_app)


@pytest.fixture()
def auth_token(client: TestClient):
    with get_session() as s:
        if not s.query(UserORM).filter(UserORM.username == "tester").first():
            s.add(UserORM(username="tester", hashed_password=hash_password("secret")))
    resp = client.post("/api/v1/auth/token", data={"username": "tester", "password": "secret"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def auth_headers(auth_token: str):
    return {"Authorization": f"Bearer {auth_token}"}
