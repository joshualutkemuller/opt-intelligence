"""Anthropic (Claude) LLM provider — reads PDFs natively via structured outputs."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .base import LLMError, LLMProvider

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-opus-4-8"


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    supports_native_pdf = True
    supports_vision = True

    def __init__(self, model: str | None = None, *, api_key: str | None = None) -> None:
        super().__init__(model or os.environ.get("DI_LLM_MODEL") or DEFAULT_MODEL)
        self._api_key = api_key or os.environ.get("DI_LLM_API_KEY")

    @staticmethod
    def is_available() -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("DI_LLM_API_KEY"))

    def _client(self):
        import anthropic

        if self._api_key:
            return anthropic.Anthropic(api_key=self._api_key)
        return anthropic.Anthropic()

    def extract(
        self,
        schema: type[T],
        *,
        instruction: str,
        system: str | None = None,
        pdf_path: Path | None = None,
        text: str | None = None,
    ) -> T:
        # Native PDF path — send the document bytes directly.
        if pdf_path is not None:
            data = base64.standard_b64encode(pdf_path.read_bytes()).decode("ascii")
            content = [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": data,
                    },
                },
                {"type": "text", "text": instruction},
            ]
        else:
            body = self._resolve_text(pdf_path, text)
            content = [{"type": "text", "text": f"{instruction}\n\n---\n{body}"}]

        message = self._client().messages.parse(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=schema,
        )
        parsed = message.parsed_output
        if parsed is None:
            raise LLMError("Anthropic returned no structured extraction.")
        return parsed

    def extract_with_images(
        self,
        schema: type[T],
        *,
        instruction: str,
        system: str | None = None,
        text: str | None = None,
        images: list[bytes] | None = None,
    ) -> T:
        content: list[dict] = []
        if text:
            content.append({"type": "text", "text": text})
        for img_bytes in (images or []):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.standard_b64encode(img_bytes).decode("ascii"),
                },
            })
        content.append({"type": "text", "text": instruction})
        message = self._client().messages.parse(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=schema,
        )
        parsed = message.parsed_output
        if parsed is None:
            raise LLMError("Anthropic returned no structured extraction.")
        return parsed

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int = 1024) -> str:
        message = self._client().messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
        return "".join(parts)
