"""Deterministic chat workflow helpers for CLI-guided optimization demos."""

from .engine import ChatResponse, ChatSession
from .parser import detect_domain, detect_scenarios

__all__ = ["ChatResponse", "ChatSession", "detect_domain", "detect_scenarios"]
