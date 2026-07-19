"""
Run deterministic IPS / policy ingestion examples.

Examples:
    python examples/run_ips_ingestion_demo.py --all
    python examples/run_ips_ingestion_demo.py \
        --workflow portfolio_rebalance_mvo \
        examples/policies/sample_mvo_ips.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from decision_intelligence.ingestion import ingest_policy_document

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = [
    (
        "portfolio_rebalance_mvo",
        REPO_ROOT / "examples/policies/sample_mvo_ips.txt",
    ),
    (
        "liquidity_stress_funding_workflow",
        REPO_ROOT / "examples/policies/sample_liquidity_ips.txt",
    ),
    (
        "collateral_liquidity_review",
        REPO_ROOT / "examples/policies/sample_collateral_policy.txt",
    ),
]

console = Console()


def main() -> None:
    args = _parse_args()
    runs = SAMPLES if args.all else [(args.workflow, args.path)]

    for workflow_id, path in runs:
        result = ingest_policy_document(
            workflow_id=workflow_id,
            text=Path(path).read_text(encoding="utf-8"),
            filename=Path(path).name,
        )
        if args.json:
            console.print_json(json.dumps(result.model_dump(), default=str))
        else:
            _print_result(workflow_id, Path(path), result.model_dump())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic IPS / policy ingestion demo samples."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=REPO_ROOT / "examples/policies/sample_mvo_ips.txt",
        help="Policy or IPS text file to ingest.",
    )
    parser.add_argument(
        "--workflow",
        default="portfolio_rebalance_mvo",
        help="Registered workflow ID to map policy fields into.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all bundled sample policy files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON responses instead of presenter tables.",
    )
    return parser.parse_args()


def _print_result(workflow_id: str, path: Path, result: dict[str, Any]) -> None:
    ready = result["review_summary"]["ready"]
    status = "[green]ready[/green]" if ready else "[yellow]needs review[/yellow]"
    console.print(
        Panel(
            f"[bold]{workflow_id}[/bold]\n"
            f"Source: {path.relative_to(REPO_ROOT)}\n"
            f"Review status: {status}",
            title="IPS Ingestion",
            border_style="cyan",
        )
    )

    fields = Table(title="Extracted Fields", show_lines=False)
    fields.add_column("Field", style="cyan", max_width=38)
    fields.add_column("Value", style="green", max_width=26)
    fields.add_column("Confidence", justify="right")
    fields.add_column("Evidence", max_width=58)
    for item in result["extracted_fields"]:
        fields.add_row(
            item["key"],
            str(item["value"]),
            f"{item['confidence']:.0%}",
            item["evidence"],
        )
    console.print(fields)

    summary = result["review_summary"]
    console.print(
        Panel(
            "\n".join(
                [
                    f"Applied fields: {summary['applied_count']}",
                    f"Missing required: {', '.join(summary['missing_required']) or 'none'}",
                    f"Warnings: {', '.join(summary['warnings']) or 'none'}",
                ]
            ),
            title="Review Summary",
            border_style="green" if ready else "yellow",
        )
    )

    console.print("[bold]Workflow context patch[/bold]")
    console.print_json(json.dumps(result["context_patch"], default=str))


if __name__ == "__main__":
    main()
