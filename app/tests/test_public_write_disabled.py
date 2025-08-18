from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import reload_settings_for_tests, settings
import os

def test_public_write_disabled(monkeypatch):
    monkeypatch.setenv('PUBLIC_WRITE_ENABLED', '0')
    monkeypatch.setenv('ENABLE_PUBLIC_ALIAS', '1')
    reload_settings_for_tests()
    app = create_app()
    client = TestClient(app)
    resp = client.post('/write-file', json={'name':'x.txt','kind':'entries','content':'hi'})
    assert resp.status_code == 403
    assert 'disabled' in resp.text.lower()
