"""
OpenAI-compatible LLM provider.

Covers OpenAI, Azure OpenAI, and any OpenAI-compatible HTTP endpoint — which is
the common interface exposed by local / offline model servers such as **Ollama**,
**vLLM**, and **llama.cpp**. Point it at one with ``DI_LLM_BASE_URL`` (or
``base_url=``); a local server typically needs no real API key.

Structured extraction uses the SDK's ``chat.completions.parse`` (native schema-
constrained decoding) when available, and falls back to JSON-schema
``response_format`` + Pydantic validation so callers always get a validated
model regardless of endpoint capabilities.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .base import LLMError, LLMProvider

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(LLMProvider):
    name = "openai"
    supports_native_pdf = False  # send extracted text

    def __init__(
        self,
        model: str | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        super().__init__(model or os.environ.get("DI_LLM_MODEL") or DEFAULT_MODEL)
        self._base_url = base_url or os.environ.get("DI_LLM_BASE_URL") or os.environ.get(
            "OPENAI_BASE_URL"
        )
        # Local servers often accept any key; default to a placeholder so the
        # SDK doesn't error on construction when talking to an offline endpoint.
        self._api_key = (
            api_key
            or os.environ.get("DI_LLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ("not-needed" if self._base_url else None)
        )

    @staticmethod
    def is_available() -> bool:
        return bool(
            os.environ.get("OPENAI_API_KEY")
            or os.environ.get("DI_LLM_API_KEY")
            or os.environ.get("DI_LLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
        )

    def _client(self):
        import openai

        kwargs = {}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._base_url:
            kwargs["base_url"] = self._base_url
        return openai.OpenAI(**kwargs)

    def extract(
        self,
        schema: type[T],
        *,
        instruction: str,
        system: str | None = None,
        pdf_path: Path | None = None,
        text: str | None = None,
    ) -> T:
        body = self._resolve_text(pdf_path, text)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": f"{instruction}\n\n---\n{body}"})

        client = self._client()

        # Preferred: native structured-output parsing.
        try:
            completion = client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=schema,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is not None:
                return parsed
        except (AttributeError, NotImplementedError):
            pass  # older SDK / endpoint without .parse — fall through
        except Exception as exc:  # noqa: BLE001 - endpoint may reject response_format
            # Fall back to JSON mode only for capability errors, not auth/network.
            if not _is_capability_error(exc):
                raise LLMError(f"OpenAI structured extraction failed: {exc}") from exc

        # Fallback: JSON-schema response_format + validate.
        return self._extract_json_fallback(client, schema, messages)

    def _extract_json_fallback(self, client, schema: type[T], messages: list) -> T:
        schema_json = schema.model_json_schema()
        guidance = (
            "Respond with ONLY a JSON object that conforms to this JSON Schema:\n"
            f"{json.dumps(schema_json)}"
        )
        msgs = [*messages, {"role": "system", "content": guidance}]
        try:
            completion = client.chat.completions.create(
                model=self.model,
                messages=msgs,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # noqa: BLE001
            # Last resort: no response_format support at all.
            completion = client.chat.completions.create(model=self.model, messages=msgs)
            if exc:  # keep the original context available for debugging
                pass

        content = completion.choices[0].message.content or ""
        try:
            return schema.model_validate_json(_strip_code_fence(content))
        except ValidationError as exc:
            raise LLMError(f"OpenAI JSON did not match schema: {exc}") from exc

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int = 1024) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        completion = self._client().chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content or ""


def _is_capability_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        s in text
        for s in ("response_format", "not supported", "unsupported", "invalid_request", "400")
    )


def _strip_code_fence(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content[: content.rfind("```")]
    return content.strip()
