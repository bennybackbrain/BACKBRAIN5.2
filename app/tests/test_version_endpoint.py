import os
os.environ['BB_TESTING'] = '1'
os.environ['ENABLE_PUBLIC_ALIAS'] = '0'
from fastapi.testclient import TestClient
from app.main import app  # import after env set so select_rate_limiter uses NoOp
client = TestClient(app)

def test_version_endpoint():
    r = client.get('/version')
    assert r.status_code == 200
    data = r.json()
    assert 'version' in data and data['version']
    assert 'specHash' in data and len(data['specHash']) >= 8
