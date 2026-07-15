"""Tests for the provider-agnostic LLM layer."""

import pytest
from pydantic import BaseModel

from decision_intelligence.llm import (
    AnthropicProvider,
    LLMConfigError,
    LLMProvider,
    OpenAIProvider,
    available_providers,
    register_provider,
    resolve_provider,
)
from decision_intelligence.llm import config as llm_config


class _Schema(BaseModel):
    domain: str
    value: int = 0


# --------------------------------------------------------------------------- #
# Config resolution
# --------------------------------------------------------------------------- #
def _clear_env(monkeypatch):
    for var in (
        "DI_LLM_PROVIDER", "DI_LLM_MODEL", "DI_LLM_BASE_URL", "DI_LLM_API_KEY",
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)


def test_resolve_none_when_nothing_configured(monkeypatch):
    _clear_env(monkeypatch)
    assert resolve_provider() is None
    assert llm_config.provider_available() is False


def test_auto_detect_anthropic(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    p = resolve_provider()
    assert isinstance(p, AnthropicProvider)
    assert p.supports_native_pdf is True


def test_auto_detect_openai_via_base_url(monkeypatch):
    """A local OpenAI-compatible endpoint (no key) is detected via base_url."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("DI_LLM_BASE_URL", "http://localhost:11434/v1")
    p = resolve_provider()
    assert isinstance(p, OpenAIProvider)
    assert p.supports_native_pdf is False
    assert p._base_url == "http://localhost:11434/v1"


def test_explicit_provider_env(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("DI_LLM_PROVIDER", "openai")
    monkeypatch.setenv("DI_LLM_MODEL", "llama3.1")
    monkeypatch.setenv("DI_LLM_BASE_URL", "http://localhost:8000/v1")
    p = resolve_provider()
    assert isinstance(p, OpenAIProvider)
    assert p.model == "llama3.1"


def test_unknown_provider_raises(monkeypatch):
    _clear_env(monkeypatch)
    with pytest.raises(LLMConfigError, match="Unknown LLM provider"):
        resolve_provider("does-not-exist")


def test_anthropic_precedence_over_openai(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-a")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-o")
    assert isinstance(resolve_provider(), AnthropicProvider)


def test_available_providers(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-o")
    assert "openai" in available_providers()
    assert "anthropic" not in available_providers()


# --------------------------------------------------------------------------- #
# Custom / offline provider registration
# --------------------------------------------------------------------------- #
def test_register_custom_provider(monkeypatch):
    _clear_env(monkeypatch)

    class LocalStub(LLMProvider):
        name = "local_stub"

        def __init__(self, model=None, base_url=None, api_key=None):
            super().__init__(model or "stub-model")

        def extract(self, schema, *, instruction, system=None, pdf_path=None, text=None):
            return schema(domain="collateral", value=1)

        def generate(self, prompt, *, system=None, max_tokens=1024):
            return "stub"

    register_provider(
        "local_stub", lambda model=None, base_url=None, api_key=None: LocalStub(model)
    )
    p = resolve_provider("local_stub")
    assert isinstance(p, LocalStub)
    out = p.extract(_Schema, instruction="x")
    assert out.domain == "collateral"


# --------------------------------------------------------------------------- #
# OpenAI provider — structured parse + JSON fallback (stubbed client)
# --------------------------------------------------------------------------- #
class _Msg:
    def __init__(self, parsed=None, content=None):
        self.parsed = parsed
        self.content = content


class _Choice:
    def __init__(self, msg):
        self.message = msg


class _Completion:
    def __init__(self, msg):
        self.choices = [_Choice(msg)]


def test_openai_native_parse(monkeypatch):
    captured = {}

    class FakeParse:
        def parse(self, **kwargs):
            captured.update(kwargs)
            return _Completion(_Msg(parsed=_Schema(domain="financing", value=3)))

    class FakeChat:
        completions = FakeParse()

    class FakeBeta:
        chat = FakeChat()

    class FakeClient:
        beta = FakeBeta()

    prov = OpenAIProvider(model="gpt-4o", api_key="k")
    monkeypatch.setattr(prov, "_client", lambda: FakeClient())
    out = prov.extract(_Schema, instruction="do it", system="sys", text="body text")
    assert out.domain == "financing" and out.value == 3
    assert captured["model"] == "gpt-4o"
    assert captured["response_format"] is _Schema


def test_openai_json_fallback(monkeypatch):
    """When .parse is unavailable, fall back to JSON mode + validation."""

    class FakeCreate:
        def create(self, **kwargs):
            return _Completion(_Msg(content='```json\n{"domain": "money_market", "value": 9}\n```'))

    class FakeParseMissing:
        def parse(self, **kwargs):
            raise AttributeError("no parse")

    class FakeChat:
        completions = FakeCreate()

    class FakeBeta:
        class chat:  # noqa: N801
            completions = FakeParseMissing()

    class FakeClient:
        beta = FakeBeta()
        chat = FakeChat()

    prov = OpenAIProvider(model="local-model", base_url="http://x/v1")
    monkeypatch.setattr(prov, "_client", lambda: FakeClient())
    out = prov.extract(_Schema, instruction="do it", text="body")
    assert out.domain == "money_market" and out.value == 9


def test_openai_generate(monkeypatch):
    class FakeCreate:
        def create(self, **kwargs):
            return _Completion(_Msg(content="hello world"))

    class FakeChat:
        completions = FakeCreate()

    class FakeClient:
        chat = FakeChat()

    prov = OpenAIProvider(model="m", api_key="k")
    monkeypatch.setattr(prov, "_client", lambda: FakeClient())
    assert prov.generate("hi") == "hello world"
