"""
Provider-agnostic LLM interface.

Every LLM-driven agent in the platform (today only the PDF intake agent; later
the Intent / Planning / Constraint / Scenario / Explanation agents) depends on
this small protocol — never on a specific vendor SDK. Concrete providers
(Anthropic, OpenAI / Azure / any OpenAI-compatible endpoint incl. local models
like Ollama / vLLM / llama.cpp) implement it and are selected by configuration.

Two capabilities:

* :meth:`LLMProvider.extract` — structured extraction of a document against a
  Pydantic schema. Providers that can read PDFs natively (Anthropic) send the
  document directly; the rest fall back to extracted text. Callers always get a
  validated model instance regardless of provider.
* :meth:`LLMProvider.generate` — free-text generation (for explanations).

Structured-output parity is the provider's responsibility: where a vendor lacks
native schema-constrained decoding, the provider must fall back to JSON mode /
tool-calling plus Pydantic validation so the return type is identical.
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when an LLM provider cannot fulfil a request."""


class LLMProvider(abc.ABC):
    """Abstract base for all LLM providers.

    Subclasses set :attr:`name` and :attr:`supports_native_pdf`, and implement
    :meth:`extract` and :meth:`generate`.
    """

    #: short identifier used in config / audit (e.g. "anthropic", "openai").
    name: str = "base"
    #: whether the provider can consume a PDF document directly.
    supports_native_pdf: bool = False

    def __init__(self, model: str) -> None:
        self.model = model

    # -- capabilities -------------------------------------------------------- #
    @abc.abstractmethod
    def extract(
        self,
        schema: type[T],
        *,
        instruction: str,
        system: str | None = None,
        pdf_path: Path | None = None,
        text: str | None = None,
    ) -> T:
        """Return a validated ``schema`` instance extracted from a document.

        Provide either ``pdf_path`` (native-PDF providers use it directly;
        others extract its text) or raw ``text``.
        """

    @abc.abstractmethod
    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int = 1024) -> str:
        """Return free-text for a prompt (used for explanations)."""

    # -- shared helpers ------------------------------------------------------ #
    @staticmethod
    def pdf_to_text(pdf_path: Path) -> str:
        """Extract text from a PDF (shared fallback for non-native providers)."""
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover
            raise LLMError(
                "Reading a PDF without a native-PDF provider needs 'pypdf' "
                "(pip install pypdf)."
            ) from exc
        reader = PdfReader(str(pdf_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _resolve_text(self, pdf_path: Path | None, text: str | None) -> str:
        if text is not None:
            return text
        if pdf_path is not None:
            return self.pdf_to_text(pdf_path)
        raise LLMError("extract() requires either 'pdf_path' or 'text'.")

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"{type(self).__name__}(name={self.name!r}, model={self.model!r})"
