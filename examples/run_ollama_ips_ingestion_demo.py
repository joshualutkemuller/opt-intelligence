"""
Run LLM-assisted IPS ingestion with a local Ollama model when available.

This keeps the deterministic validator in the loop: Ollama proposes fields, and
the IPS ingestion layer filters, coerces, and validates them before producing a
workflow context patch.

Run from the repo root:
    python examples/run_ollama_ips_ingestion_demo.py
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from decision_intelligence.ingestion import IngestionError, ingest_policy_document
from decision_intelligence.llm import LLMConfigError, resolve_provider

console = Console(width=120)
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b"


def main() -> int:
    args = _parse_args()
    base_url = _normalize_url(args.ollama_url)
    pdf_path = Path(args.pdf)

    console.print(
        Panel(
            "[bold blue]Ollama IPS Ingestion Demo[/bold blue]\n\n"
            f"[dim]Ollama:[/dim] {base_url}\n"
            f"[dim]Model:[/dim]  {args.model}\n"
            f"[dim]PDF:[/dim]    {pdf_path}",
            border_style="blue",
            padding=(1, 2),
        )
    )

    if not _ollama_available(base_url, args.timeout):
        console.print("[yellow]Ollama is not available. Skipping LLM IPS demo.[/yellow]")
        console.print("[dim]Start with: ollama serve[/dim]")
        console.print(f"[dim]Pull model: ollama pull {args.model}[/dim]")
        return 1 if args.strict else 0

    if not pdf_path.exists():
        console.print(f"[red]PDF not found:[/red] {pdf_path}")
        return 1

    try:
        provider = resolve_provider(
            "openai",
            model=args.model,
            base_url=f"{base_url}/v1",
            api_key="not-needed",
        )
    except LLMConfigError as exc:
        console.print(f"[red]Provider resolution failed:[/red] {exc}")
        return 1 if args.strict else 0
    if provider is None:
        console.print("[red]Could not resolve OpenAI-compatible provider.[/red]")
        return 1 if args.strict else 0

    try:
        result = ingest_policy_document(
            workflow_id=args.workflow,
            pdf_base64=base64.b64encode(pdf_path.read_bytes()).decode("utf-8"),
            filename=pdf_path.name,
            backend="llm",
            provider=provider,
        )
    except IngestionError as exc:
        console.print(f"[red]LLM-assisted IPS ingestion failed:[/red] {exc}")
        console.print(
            "[dim]Try deterministic mode with: "
            "python examples/run_ips_ingestion_demo.py[/dim]"
        )
        return 1 if args.strict else 0

    console.print("[green]LLM-assisted IPS ingestion completed.[/green]")
    console.print_json(result.model_dump_json())
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local Ollama IPS ingestion demo.")
    parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_URL))
    parser.add_argument("--model", default=os.environ.get("DI_LLM_MODEL", DEFAULT_MODEL))
    parser.add_argument("--workflow", default="portfolio_rebalance_mvo")
    parser.add_argument("--pdf", default="examples/policies/sample_full_ips.pdf")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def _normalize_url(raw_url: str) -> str:
    url = raw_url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


def _ollama_available(base_url: str, timeout: float) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=timeout):
            return True
    except (OSError, urllib.error.URLError):
        return False


if __name__ == "__main__":
    raise SystemExit(main())
