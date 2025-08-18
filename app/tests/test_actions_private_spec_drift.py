import subprocess
from pathlib import Path

SPEC = Path("actions/openapi-actions-private.yaml")
HASH = Path("openapi-actions-private.sha256")

def test_actions_private_spec_is_frozen():
    assert SPEC.exists(), "private Actions spec missing"
    assert HASH.exists(), "private Actions spec hash missing"
    res = subprocess.run([
        "python3", "scripts/spec_hash.py", str(SPEC)
    ], check=True, capture_output=True, text=True)
    got = res.stdout.strip()
    expected = HASH.read_text().strip()
    assert got == expected, f"private Actions spec drift:\n expected={expected}\n got={got}"
