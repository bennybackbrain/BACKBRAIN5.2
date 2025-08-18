from __future__ import annotations

def test_entries_list_uses_webdav(monkeypatch):
    from app.api import public_alias as pa

    # Configure unified entries dir
    pa.get_settings().inbox_dir = "BACKBRAIN5.2/entries"

    # Force DB failure by raising when context manager entered
    class BrokenCtx:
        def __enter__(self):  # pragma: no cover
            raise RuntimeError("db down")
        def __exit__(self, exc_type, exc, tb):  # pragma: no cover
            return False

    monkeypatch.setattr(pa, "get_session", lambda: BrokenCtx())

    # Simulate WebDAV list
    monkeypatch.setattr(pa, "list_dir", lambda base: [f"{pa.get_settings().inbox_dir}/x.md", f"{pa.get_settings().inbox_dir}/y.md"])  # type: ignore[attr-defined]
    monkeypatch.setattr(pa, "mkdirs", lambda base: True)  # type: ignore[attr-defined]

    resp = pa.public_list_files(kind="entries")
    assert resp.kind == "entries"
    assert sorted(resp.files) == ["x.md", "y.md"]
