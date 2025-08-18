import re

def rank_by_query_heuristic(q: str, texts: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Sehr einfache, deterministische Rangfolge:
       - Case-insensitive Substrings
       - leichte Gewichtung von Titeln/Frontmatter
       - stabile Sortierung
    """
    ql = q.lower().strip()
    def score(item: tuple[str, str]) -> tuple[int, int]:
        name, content = item
        c = content.lower()
        hits = c.count(ql) if ql else 0
        first = c.find(ql) if ql and ql in c else 1_000_000
        return (hits, -first)
    return sorted(texts, key=score, reverse=True)
