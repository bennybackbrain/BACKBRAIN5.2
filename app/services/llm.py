from __future__ import annotations
"""LLM chat service abstraction.

Provides a unified chat() function which attempts to call OpenAI if an API key
is configured, otherwise falls back to a lightweight heuristic echo model.
"""
from typing import List, Dict, Any, TypedDict, cast
import logging
from app.core.config import settings

logger = logging.getLogger("app.llm")

def _heuristic_reply(messages: List[Dict[str, str]]) -> str:
    # Very small "nano" style summarizing/echo: take last user content and truncate.
    last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    if not last_user:
        return "(no input)"
    snippet = last_user.strip().split()
    snippet = snippet[:60]
    text = " ".join(snippet)
    if len(text) > 400:
        text = text[:397] + "..."
    return f"Heuristic response: {text}"

class _ChatMessage(TypedDict, total=False):
    role: str
    content: str

def chat(messages: List[Dict[str, str]], model: str | None = None) -> Dict[str, Any]:
    """Return a chat completion dict with keys: model, content.

    If OPENAI_API_KEY present and openai library import succeeds, perform a real call.
    Network / import / API errors fall back to heuristic reply (never raise to caller).
    """
    chosen_model = model or settings.summary_model
    api_key = settings.openai_api_key
    if not api_key:
        return {"model": "heuristic", "content": _heuristic_reply(messages)}
    try:
        import openai  # type: ignore
        client = openai.OpenAI(api_key=api_key)  # type: ignore[attr-defined]
        # Cast to expected iterable of typed message params (simplified)
        resp = client.chat.completions.create(  # type: ignore[attr-defined]
            model=chosen_model,
            messages=cast(Any, messages),  # messages are simple role/content dicts
            temperature=0.3,
            max_tokens=300,
        )
        choice = resp.choices[0]  # type: ignore[index]
        content = getattr(choice.message, "content", None) or ""
        if not content:
            content = _heuristic_reply(messages)
        return {"model": chosen_model, "content": content}
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm_fallback", extra={"error": str(exc)[:120]})
        return {"model": "heuristic", "content": _heuristic_reply(messages)}


def call_llm(system: str, user: str, model: str, max_tokens: int = 800):
    """Wrapper für Query-Endpoint: ruft chat() und gibt nur den Content zurück."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
    result = chat(messages, model=model)
    return result.get("content", "(no result)")

__all__ = ["chat", "call_llm"]
