from __future__ import annotations

def test_public_get_all_summaries_webdav_fallback(monkeypatch):
    """If DB access fails, endpoint should fall back to WebDAV and still return 200 structure."""
    from app.api import public_alias as pa

    # Force DB path to raise when context manager used
    class BrokenCtx:
        def __enter__(self):  # pragma: no cover
            raise RuntimeError("DB down")
        def __exit__(self, exc_type, exc, tb):  # pragma: no cover
            return False

    monkeypatch.setattr(pa, "get_session", lambda: BrokenCtx())

    pa.get_settings().summaries_dir = "BACKBRAIN5.2/summaries"

    monkeypatch.setattr(pa, "get_file_content", lambda rel: "Summary content for " + rel)
    # Provide list_dir + mkdirs if imported inside function
    monkeypatch.setattr(pa, "list_dir", lambda base: [f"{base}/a.md", f"{base}/b.md"])  # type: ignore[attr-defined]
    monkeypatch.setattr(pa, "mkdirs", lambda base: True)  # type: ignore[attr-defined]

    resp = pa.public_get_all_summaries()
    assert hasattr(resp, "summaries")
    assert len(resp.summaries) == 2
    names = sorted([s.name for s in resp.summaries])
    assert names == ["a.md", "b.md"]
    for item in resp.summaries:
        assert item.content.startswith("Summary content for")
