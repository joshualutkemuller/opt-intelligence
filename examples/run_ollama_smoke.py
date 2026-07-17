"""
Offline Ollama smoke test for the provider-agnostic LLM ingestion path.

This script is intentionally dynamic:
  - skips cleanly if Ollama is not running,
  - picks an available lightweight model unless one is supplied,
  - verifies the OpenAI-compatible provider resolves,
  - runs PDF LLM ingestion as a dry-run,
  - routes the resulting OptimizationRequest through the optimizer pipeline.

Run from the repo root:
    python examples/run_ollama_smoke.py

Use --strict in CI-like checks when Ollama is expected to be available.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from decision_intelligence.ingestion import IngestionError, ingest_pdf
from decision_intelligence.llm import LLMConfigError, resolve_provider
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)

console = Console(width=120)

DEFAULT_OLLAMA_URL = "http://localhost:11434"
PREFERRED_MODELS = (
    "llama3.2:3b",
    "llama3.2:1b",
    "qwen2.5:3b",
    "qwen2.5:1.5b",
    "llama3.1:8b",
    "llama3.1",
)


@dataclass(frozen=True)
class ProbeResult:
    available: bool
    models: list[str]
    message: str = ""


def main() -> int:
    args = _parse_args()
    base_url = normalize_url(args.ollama_url)
    pdf_path = Path(args.pdf)

    console.print()
    console.print(Panel(
        "[bold blue]Ollama Offline LLM Smoke Test[/bold blue]\n\n"
        f"[dim]Ollama:[/dim] {base_url}\n"
        f"[dim]PDF:[/dim]    {pdf_path}",
        border_style="blue",
        padding=(1, 2),
    ))

    probe = probe_ollama(base_url, timeout=args.timeout)
    if not probe.available:
        return _skip_or_fail(
            args.strict,
            f"Ollama is not available: {probe.message}",
            [
                "Start Ollama with: ollama serve",
                "Pull a model with: ollama pull llama3.2:3b",
            ],
        )

    model = choose_model(probe.models, requested=args.model)
    if model is None:
        return _skip_or_fail(
            args.strict,
            "Ollama is running, but no usable model was found.",
            [
                f"Installed models: {', '.join(probe.models) or 'none'}",
                "Pull one with: ollama pull llama3.2:3b",
            ],
        )

    missing = missing_optional_packages()
    if missing:
        return _skip_or_fail(
            args.strict,
            f"Missing optional packages: {', '.join(missing)}",
            ['Install with: pip install -e ".[ingest,llm-openai]"'],
        )

    if not pdf_path.exists():
        return _skip_or_fail(args.strict, f"PDF not found: {pdf_path}", [])

    provider = resolve_ollama_provider(model, base_url)
    if provider is None:
        return 1 if args.strict else 0

    request = run_ingestion(pdf_path, provider, args.seed)
    if request is None:
        return 1 if args.strict else 0

    result = run_optimizer(request)
    render_summary(model, request, result)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local Ollama LLM ingestion smoke test.")
    parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_URL))
    parser.add_argument("--model", default=os.environ.get("DI_LLM_MODEL"))
    parser.add_argument("--pdf", default="examples/sample_brief.pdf")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when Ollama/model/dependencies are unavailable.",
    )
    return parser.parse_args()


def probe_ollama(base_url: str, *, timeout: float = 2.0) -> ProbeResult:
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except (OSError, urllib.error.URLError) as exc:
        return ProbeResult(False, [], str(exc))

    try:
        import json

        data = json.loads(payload)
        models = sorted(
            item.get("name", "")
            for item in data.get("models", [])
            if item.get("name")
        )
        return ProbeResult(True, models)
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(False, [], f"Could not parse /api/tags response: {exc}")


def normalize_url(raw_url: str) -> str:
    url = raw_url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


def choose_model(models: list[str], *, requested: str | None = None) -> str | None:
    if requested:
        return requested if requested in models else None
    model_set = set(models)
    for preferred in PREFERRED_MODELS:
        if preferred in model_set:
            return preferred
    return models[0] if models else None


def missing_optional_packages() -> list[str]:
    missing = []
    for package in ("openai", "pypdf"):
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    return missing


def resolve_ollama_provider(model: str, ollama_url: str):
    os.environ["DI_LLM_PROVIDER"] = "openai"
    os.environ["DI_LLM_BASE_URL"] = f"{ollama_url.rstrip('/')}/v1"
    os.environ["DI_LLM_MODEL"] = model
    os.environ.setdefault("DI_LLM_API_KEY", "not-needed")

    try:
        provider = resolve_provider("openai", model=model)
    except LLMConfigError as exc:
        console.print(f"[red]Provider resolution failed:[/red] {exc}")
        return None

    console.print(
        f"[green]Provider resolved[/green]: {provider.name} / {provider.model} "
        f"({os.environ['DI_LLM_BASE_URL']})"
    )
    return provider


def run_ingestion(pdf_path: Path, provider: Any, seed: int):
    console.print("[cyan]Running LLM ingestion dry-run...[/cyan]")
    try:
        request, extracted = ingest_pdf(pdf_path, backend="llm", seed=seed, provider=provider)
    except IngestionError as exc:
        console.print(f"[red]LLM ingestion failed:[/red] {exc}")
        console.print(
            "[dim]Tip: try a stronger local model or run the deterministic fallback:[/dim]"
        )
        console.print("[dim]  di ingest examples/sample_brief.pdf --backend heuristic[/dim]")
        return None

    console.print(
        "[green]Dry-run extracted[/green]: "
        f"domain={extracted.domain}, objective={extracted.objective_metric}, "
        f"scenarios={', '.join(extracted.scenarios) or 'none'}"
    )
    return request


def run_optimizer(request):
    console.print("[cyan]Running mapped optimizer request...[/cyan]")
    registry = OptimizerRegistry()
    registry.register(CollateralOptimizer())
    registry.register(MoneyMarketOptimizer())
    registry.register(FinancingOptimizer())
    return OptimizationOrchestrator(registry).run(request)


def render_summary(model: str, request, result) -> None:
    table = Table(title="Ollama LLM Smoke Test Result")
    table.add_column("Check", style="cyan")
    table.add_column("Value")
    table.add_row("Model", model)
    table.add_row("Domain", request.domain)
    table.add_row("Objective", request.objective.metric)
    table.add_row("Status", str(result.status.value))
    table.add_row("Objective Value", f"{result.objective_value:,.4f}")
    table.add_row("Allocations", str(len(result.allocations)))
    table.add_row("Validation", result.validation_report.recommendation)
    console.print(table)


def _skip_or_fail(strict: bool, message: str, next_steps: list[str]) -> int:
    style = "red" if strict else "yellow"
    label = "FAILED" if strict else "SKIPPED"
    console.print(f"[{style}]{label}[/{style}]: {message}")
    for step in next_steps:
        console.print(f"  - {step}")
    return 1 if strict else 0


if __name__ == "__main__":
    sys.exit(main())
