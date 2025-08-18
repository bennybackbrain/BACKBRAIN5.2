#!/usr/bin/env python3
"""Generate canonical hash of current app OpenAPI and write actions/openapi-public.sha256.
Skips if placeholder spec file detected.
"""
import json, hashlib, sys, pathlib
from typing import Any, Dict
from app.main import app

SPEC_PATH = pathlib.Path('actions/openapi-public.json')
HASH_PATH = pathlib.Path('actions/openapi-public.sha256')

if not SPEC_PATH.exists():
    print("Spec file missing", file=sys.stderr)
    sys.exit(1)
raw = SPEC_PATH.read_text().strip()
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print("Spec file not valid JSON", file=sys.stderr)
    sys.exit(1)
if 'note' in data and 'fetch_url' in data:
    print("Placeholder spec detected; not hashing.")
    sys.exit(0)

def normalize(spec: Dict[str, Any]) -> Dict[str, Any]:
    spec = dict(spec)  # shallow copy
    spec.pop('servers', None)
    # Remove description volatility
    return spec

live = normalize(app.openapi())
canonical = json.dumps(live, sort_keys=True, separators=(',',':')).encode()
sha = hashlib.sha256(canonical).hexdigest()
HASH_PATH.write_text(sha + "\n")
print("Wrote", HASH_PATH, sha)
