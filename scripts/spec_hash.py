#!/usr/bin/env python3
"""Generate canonical hash for a JSON or YAML OpenAPI spec file.

Usage:
  python scripts/spec_hash.py            # hashes actions/openapi-public.json -> actions/openapi-public.sha256
  python scripts/spec_hash.py path.yaml  # prints hash to stdout only (no write unless second arg given)
  python scripts/spec_hash.py path.yaml output.sha256  # writes hash file and prints hash
"""
import json, hashlib, sys, pathlib
from typing import Any, Dict

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

def load_spec(path: pathlib.Path):
    raw = path.read_text().strip()
    if path.suffix.lower() in {'.yaml', '.yml'}:
        if not yaml:
            print("PyYAML not installed", file=sys.stderr)
            sys.exit(1)
        return yaml.safe_load(raw)
    return json.loads(raw)

def normalize(spec: Dict[str, Any]) -> Dict[str, Any]:
    spec = dict(spec)
    spec.pop('servers', None)
    return spec

def main():  # pragma: no cover
    args = sys.argv[1:]
    if not args:
        # public default mode uses live app schema to ensure drift detection consistent
        from app.main import app
        spec_path = pathlib.Path('actions/openapi-public.json')
        hash_path = pathlib.Path('actions/openapi-public.sha256')
        if not spec_path.exists():
            print('Spec file missing', file=sys.stderr)
            sys.exit(1)
        data = load_spec(spec_path)
        if isinstance(data, dict) and 'note' in data and 'fetch_url' in data:
            print('Placeholder spec detected; not hashing.')
            sys.exit(0)
        live = normalize(app.openapi())
        canonical = json.dumps(live, sort_keys=True, separators=(',',':')).encode()
        sha = hashlib.sha256(canonical).hexdigest()
        hash_path.write_text(sha + '\n')
        print('Wrote', hash_path, sha)
        return
    spec_path = pathlib.Path(args[0])
    if not spec_path.exists():
        print('Spec path missing', file=sys.stderr)
        sys.exit(1)
    data = load_spec(spec_path)
    canonical = json.dumps(normalize(data), sort_keys=True, separators=(',',':')).encode()
    sha = hashlib.sha256(canonical).hexdigest()
    if len(args) > 1:
        pathlib.Path(args[1]).write_text(sha + '\n')
    print(sha)

if __name__ == '__main__':  # pragma: no cover
    main()
