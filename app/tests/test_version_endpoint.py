from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_version_endpoint():
    r = client.get('/version')
    assert r.status_code == 200
    data = r.json()
    assert 'version' in data and data['version']
    assert 'specHash' in data and len(data['specHash']) >= 8
