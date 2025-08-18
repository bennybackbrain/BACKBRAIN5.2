import json, hashlib
from app.main import app, settings
from pathlib import Path
import pytest
from typing import Any, Dict

SPEC_FILE = Path('actions/openapi-public.json')
HASH_FILE = Path('actions/openapi-public.sha256')


def _normalize(d: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(d)  # shallow copy
    d.pop('servers', None)
    return d


def test_spec_drift():
    assert SPEC_FILE.exists(), "Committed spec file missing"
    content = SPEC_FILE.read_text().strip()
    data = json.loads(content)
    if 'note' in data and 'fetch_url' in data:
        pytest.skip('Placeholder spec present; drift check skipped until real spec frozen.')
    # Skip drift check if public alias disabled but spec includes them
    if not settings.enable_public_alias:
        pytest.skip('Public alias disabled in test env; spec drift check skipped.')
    # App spec
    live = _normalize(app.openapi())
    committed = _normalize(data)
    canon_live = json.dumps(live, sort_keys=True, separators=(',',':')).encode()
    canon_committed = json.dumps(committed, sort_keys=True, separators=(',',':')).encode()
    if canon_live != canon_committed:
        # compute hashes for debug
        h_live = hashlib.sha256(canon_live).hexdigest()
        h_comm = hashlib.sha256(canon_committed).hexdigest()
        raise AssertionError(f"OpenAPI spec drift detected:\n live={h_live}\n committed={h_comm}")
