import os
from app.services.summarizer import write_summary_dual, read_summary_preferring_cache

def test_dual_write_and_read(tmp_path):
    stem = "testcache"
    content = "Testinhalt für Cache und Nextcloud."
    cache_dir = tmp_path / "summaries"
    os.makedirs(cache_dir, exist_ok=True)
    # Simuliere ENV
    os.environ["SUMMARY_CACHE_ENABLED"] = "true"
    os.environ["SUMMARY_CACHE_DIR"] = str(cache_dir)
    write_summary_dual(stem, content)
    result = read_summary_preferring_cache(stem)
    assert result == content
