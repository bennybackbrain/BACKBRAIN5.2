from importlib import reload
import pytest
from typing import Any


def test_openai_key_guard_blocks_without_confirm(monkeypatch: Any):  # type: ignore[override]
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-THISISAREALISTICLOOKINGKEY012345678901234567890")
    monkeypatch.delenv("CONFIRM_USE_PROD_KEY", raising=False)
    from app import core  # type: ignore
    reload(core.config)  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError):
        from app import main  # type: ignore
        reload(main)


def test_openai_key_guard_allows_with_confirm(monkeypatch: Any):  # type: ignore[override]
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-THISISAREALISTICLOOKINGKEY012345678901234567890")
    monkeypatch.setenv("CONFIRM_USE_PROD_KEY", "1")
    from app import core  # type: ignore
    reload(core.config)  # type: ignore[attr-defined]
    from app import main  # type: ignore
    reload(main)
    assert hasattr(main, 'app')
