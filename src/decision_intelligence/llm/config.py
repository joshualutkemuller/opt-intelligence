"""
Configuration-driven LLM provider selection.

Priority order (highest wins):
  1. Arguments passed directly to :func:`resolve_provider`.
  2. Environment variables:
       DI_LLM_PROVIDER   anthropic | openai | <registered name>
       DI_LLM_MODEL      model id
       DI_LLM_BASE_URL   OpenAI-compatible endpoint (Ollama / vLLM / Azure)
       DI_LLM_API_KEY    generic key (also ANTHROPIC_API_KEY / OPENAI_API_KEY)
  3. ``config/llm.yaml`` in the repository root — edit this file to set a
     default provider, model, and (optionally) API key without touching env vars.

When no provider is named, one is auto-detected from available credentials:
Anthropic if ``ANTHROPIC_API_KEY`` is set, else an OpenAI-compatible endpoint if
``OPENAI_API_KEY`` / ``DI_LLM_BASE_URL`` is set, else ``None`` (callers then use
the deterministic offline path).

Additional providers can be registered at runtime with :func:`register_provider`.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider
from .openai_provider import OpenAIProvider

# ---------------------------------------------------------------------------
# config/llm.yaml loader — read once at import time, never raises
# ---------------------------------------------------------------------------

def _load_yaml_config() -> dict:
    """Return the parsed config/llm.yaml, or {} if absent / unreadable."""
    try:
        import yaml  # PyYAML — optional; stdlib tomllib is 3.11+ only
    except ImportError:
        return {}
    # Walk up from this file to find the repo root (contains pyproject.toml).
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "config" / "llm.yaml"
        if candidate.exists():
            try:
                data = yaml.safe_load(candidate.read_text()) or {}
                return data if isinstance(data, dict) else {}
            except Exception:  # noqa: BLE001
                return {}
    return {}


_YAML_CFG: dict = _load_yaml_config()


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

# name → availability predicate (credentials/base URL configured)
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
    """Names of registered providers with enough configuration to be selected."""
    return [n for n, check in _AVAILABILITY.items() if _safe(check)]


def _safe(check: Callable[[], bool]) -> bool:
    try:
        return bool(check())
    except Exception:  # noqa: BLE001 - availability probing must never raise
        return False


def _yaml(key: str) -> str | None:
    """Return a non-empty string value from the YAML config, or None."""
    v = _YAML_CFG.get(key)
    return str(v).strip() or None if v else None


def _auto_detect() -> str | None:
    # 1. explicit env var
    explicit = os.environ.get("DI_LLM_PROVIDER")
    if explicit:
        return explicit.strip().lower()
    # 2. credentials already set → pick matching provider
    for name in ("anthropic", "openai"):
        if name in _AVAILABILITY and _safe(_AVAILABILITY[name]):
            return name
    # 3. config/llm.yaml provider + inject its api_key into env so is_available() passes
    yaml_provider = _yaml("provider")
    if yaml_provider:
        yaml_key = _yaml("api_key")
        if yaml_key and not os.environ.get("DI_LLM_API_KEY"):
            os.environ["DI_LLM_API_KEY"] = yaml_key
        if yaml_provider in _AVAILABILITY and _safe(_AVAILABILITY[yaml_provider]):
            return yaml_provider.lower()
        # Provider named in YAML but no key anywhere — still return it so the
        # caller gets a clear LLMConfigError rather than silent None.
        return yaml_provider.lower()
    return None


def resolve_provider(
    name: str | None = None,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> LLMProvider | None:
    """Resolve a provider by name/config, or ``None`` if none is configured.

    Resolution order: explicit args → env vars → config/llm.yaml → None.
    An explicitly requested provider that is unknown raises :class:`LLMConfigError`.
    """
    chosen = name or _auto_detect()
    if chosen is None:
        return None
    chosen = chosen.strip().lower()
    if chosen not in _REGISTRY:
        raise LLMConfigError(
            f"Unknown LLM provider '{chosen}'. Registered: {sorted(_REGISTRY)}"
        )
    # Fill gaps from YAML when the caller didn't supply them.
    resolved_model = model or os.environ.get("DI_LLM_MODEL") or _yaml("model")
    resolved_url = base_url or os.environ.get("DI_LLM_BASE_URL") or _yaml("base_url")
    resolved_key = (
        api_key
        or os.environ.get("DI_LLM_API_KEY")
        or _yaml("api_key")
    )
    try:
        return _REGISTRY[chosen](
            model=resolved_model, base_url=resolved_url, api_key=resolved_key
        )
    except Exception as exc:  # noqa: BLE001
        raise LLMConfigError(f"Could not construct provider '{chosen}': {exc}") from exc


def provider_available() -> bool:
    """True when some LLM provider is configured and usable."""
    return _auto_detect() is not None
