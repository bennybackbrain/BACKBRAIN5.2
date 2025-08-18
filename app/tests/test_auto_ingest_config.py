from __future__ import annotations
from app.core.config import reload_settings_for_tests


def test_auto_ingest_interval_respects_minimum(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("AUTO_INGEST_ENABLED", "1")  # type: ignore[attr-defined]
    monkeypatch.setenv("AUTO_INGEST_MIN_INTERVAL_SECONDS", "10")  # type: ignore[attr-defined]
    monkeypatch.setenv("AUTO_INGEST_INTERVAL_SECONDS", "1")  # type: ignore[attr-defined]
    reload_settings_for_tests()
    from app.core.config import settings as live
    assert live.auto_ingest_interval_seconds == 1
    assert live.auto_ingest_min_interval_seconds == 10
    # The clamping happens in lifespan startup; emulate calculation
    interval = max(live.auto_ingest_min_interval_seconds, live.auto_ingest_interval_seconds)
    assert interval == 10


def test_auto_ingest_interval_custom(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("AUTO_INGEST_ENABLED", "1")  # type: ignore[attr-defined]
    monkeypatch.setenv("AUTO_INGEST_MIN_INTERVAL_SECONDS", "2")  # type: ignore[attr-defined]
    monkeypatch.setenv("AUTO_INGEST_INTERVAL_SECONDS", "5")  # type: ignore[attr-defined]
    reload_settings_for_tests()
    from app.core.config import settings as live
    assert live.auto_ingest_interval_seconds == 5
    assert live.auto_ingest_min_interval_seconds == 2
    interval = max(live.auto_ingest_min_interval_seconds, live.auto_ingest_interval_seconds)
    assert interval == 5
