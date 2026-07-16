"""Deterministic chat workflow helpers for CLI-guided optimization demos."""

from .parser import detect_domain, detect_scenarios

__all__ = ["ChatResponse", "ChatSession", "detect_domain", "detect_scenarios"]


def __getattr__(name: str):
    if name in {"ChatResponse", "ChatSession"}:
        from .engine import ChatResponse, ChatSession

        return {"ChatResponse": ChatResponse, "ChatSession": ChatSession}[name]
    raise AttributeError(name)
