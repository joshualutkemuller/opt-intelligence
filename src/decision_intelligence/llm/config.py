"""
Configuration-driven LLM provider selection.

The provider is chosen — not coded — via arguments or environment:

    DI_LLM_PROVIDER   anthropic | openai | <registered name>   (explicit choice)
    DI_LLM_MODEL      model id (provider-specific default otherwise)
    DI_LLM_BASE_URL   OpenAI-compatible endpoint (local models: Ollama/vLLM/…)
    DI_LLM_API_KEY    generic key (falls back to ANTHROPIC_API_KEY / OPENAI_API_KEY)

When no provider is named, one is auto-detected from available credentials:
Anthropic if ``ANTHROPIC_API_KEY`` is set, else an OpenAI-compatible endpoint if
``OPENAI_API_KEY`` / ``DI_LLM_BASE_URL`` is set, else ``None`` (callers then use
the deterministic offline path).

Additional providers can be registered at runtime with :func:`register_provider`.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider
from .openai_provider import OpenAIProvider


class LLMConfigError(ValueError):
    """Raised when a provider is requested but cannot be constructed."""


# name → factory(model, base_url, api_key) -> LLMProvider
ProviderFactory = Callable[..., LLMProvider]

_REGISTRY: dict[str, ProviderFactory] = {
    "anthropic": lambda model=None, base_url=None, api_key=None: AnthropicProvider(
        model, api_key=api_key
    ),
    "openai": lambda model=None, base_url=None, api_key=None: OpenAIProvider(
        model, base_url=base_url, api_key=api_key
    ),
}

# name → availability predicate (credentials present + SDK importable)
_AVAILABILITY: dict[str, Callable[[], bool]] = {
    "anthropic": AnthropicProvider.is_available,
    "openai": OpenAIProvider.is_available,
}


def register_provider(
    name: str,
    factory: ProviderFactory,
    *,
    is_available: Callable[[], bool] | None = None,
) -> None:
    """Register a custom provider factory (e.g. an in-house or offline model)."""
    _REGISTRY[name] = factory
    if is_available is not None:
        _AVAILABILITY[name] = is_available


def available_providers() -> list[str]:
    """Names of registered providers whose credentials/SDK are currently present."""
    return [n for n, check in _AVAILABILITY.items() if _safe(check)]


def _safe(check: Callable[[], bool]) -> bool:
    try:
        return bool(check())
    except Exception:  # noqa: BLE001 - availability probing must never raise
        return False


def _auto_detect() -> str | None:
    explicit = os.environ.get("DI_LLM_PROVIDER")
    if explicit:
        return explicit.strip().lower()
    for name in ("anthropic", "openai"):
        if name in _AVAILABILITY and _safe(_AVAILABILITY[name]):
            return name
    return None


def resolve_provider(
    name: str | None = None,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> LLMProvider | None:
    """Resolve a provider by name/config, or ``None`` if none is configured.

    An explicitly requested provider that is unknown raises :class:`LLMConfigError`.
    """
    chosen = (name or _auto_detect())
    if chosen is None:
        return None
    chosen = chosen.strip().lower()
    if chosen not in _REGISTRY:
        raise LLMConfigError(
            f"Unknown LLM provider '{chosen}'. Registered: {sorted(_REGISTRY)}"
        )
    try:
        return _REGISTRY[chosen](model=model, base_url=base_url, api_key=api_key)
    except Exception as exc:  # noqa: BLE001
        raise LLMConfigError(f"Could not construct provider '{chosen}': {exc}") from exc


def provider_available() -> bool:
    """True when some LLM provider is configured and usable."""
    return _auto_detect() is not None
