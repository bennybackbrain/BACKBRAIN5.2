import os
from typing import Iterator, Tuple
from app.core.config import get_summary_cache_enabled, get_summary_cache_dir

def iter_cached_summaries(limit_files: int = 500) -> Iterator[Tuple[str, str]]:
    if not get_summary_cache_enabled():
        return iter(())
    base = get_summary_cache_dir()
    try:
        names = [n for n in os.listdir(base) if n.endswith(".summary.md")]
    except FileNotFoundError:
        names = []
    names.sort()
    for name in names[:limit_files]:
        p = os.path.join(base, name)
        try:
            with open(p, "r", encoding="utf-8") as f:
                yield name, f.read()
        except Exception:
            continue
