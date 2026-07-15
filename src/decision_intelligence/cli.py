"""
di — Decision Intelligence Platform CLI

Commands:
  di list                             List registered optimizer domains
  di info <domain>                    Describe a domain's capabilities
  di run <domain> [OPTIONS]           Run an optimization
  di run <domain> --scenario stress   Run with scenario analysis
  di ingest <file.pdf>                Parse a PDF brief into a request and solve
"""

import json
import sys
from pathlib import Path
from typing import Optional

try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
except ImportError:
    print("Install: pip install 'decision-intelligence[dev]' typer")
    sys.exit(1)

from decision_intelligence.contracts import (
    Objective,
    ObjectiveDirection,
    OptimizationRequest,
    Scenario,
)
from decision_intelligence.contracts.requests import ExecutionMode
from decision_intelligence.contracts.results import SolveStatus
from decision_intelligence.contracts.scenarios import ScenarioType
from decision_intelligence.export import export_csv, export_json, generate_report
from decision_intelligence.governance.audit import AuditLog
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)

app = typer.Typer(
    name="di",
    help="Decision Intelligence Platform — optimization orchestrator",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

console = Console()

_DOMAIN_INFO = {
    "collateral": {
        "desc": "Minimize funding cost across collateral assets subject to eligibility, haircut coverage, inventory, and concentration constraints.",
        "objective": "funding_cost",
        "direction": ObjectiveDirection.MINIMIZE,
        "metrics": ["funding_cost", "haircut_cost", "opportunity_cost"],
        "default_context": {"n_assets": 20, "seed": 42},
    },
    "money_market": {
        "desc": "Maximize net yield across money market funds subject to daily/weekly liquidity floors, WAM cap, prime concentration, and single-fund limits.",
        "objective": "yield",
        "direction": ObjectiveDirection.MAXIMIZE,
        "metrics": ["yield", "net_yield", "expense_ratio"],
        "default_context": {"n_funds": 8, "seed": 42, "total_cash": 500_000_000},
    },
    "financing": {
        "desc": "Minimize financing spread cost across counterparties subject to tenor compatibility, capacity, concentration, and capital budget.",
        "objective": "funding_spread",
        "direction": ObjectiveDirection.MINIMIZE,
        "metrics": ["funding_spread", "capital_usage", "funding_cost"],
        "default_context": {"n_counterparties": 10, "seed": 42, "total_funding_need": 300_000_000},
    },
}

_SCENARIO_PRESETS = {
    "stress": {
        "collateral":   {"obligation_scale": 1.5},
        "money_market": {"daily_liquidity_req": 0.40, "weekly_liquidity_req": 0.70},
        "financing":    {"spread_shift": 1.5, "capacity_scale": 0.6},
    },
    "credit_stress": {
        "collateral":   {"obligation_scale": 1.3},
        "money_market": {"daily_liquidity_req": 0.45, "yield_shift": 0.92},
        "financing":    {"spread_shift": 1.5, "capacity_scale": 0.6},
    },
    "downside": {
        "collateral":   {"inventory_scale": 0.7},
        "money_market": {"yield_shift": 0.9},
        "financing":    {"spread_shift": 1.2, "capacity_scale": 0.8},
    },
    "inventory": {
        "collateral":   {"inventory_scale": 0.7},
        "money_market": {},
        "financing":    {},
    },
}


def _build_registry() -> tuple[OptimizationOrchestrator, AuditLog]:
    audit = AuditLog()
    reg = OptimizerRegistry()
    reg.register(CollateralOptimizer())
    reg.register(MoneyMarketOptimizer())
    reg.register(FinancingOptimizer())
    return OptimizationOrchestrator(reg, audit), audit


def _bar(frac: float, width: int = 24) -> str:
    frac = max(0.0, min(1.0, frac))
    filled = round(frac * width)
    empty = width - filled
    return "█" * max(0, filled - 1) + ("▓" if filled else "") + "░" * empty


@app.command("list")
def cmd_list():
    """List all registered optimization domains."""
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold blue")
    table.add_column("Domain", style="cyan")
    table.add_column("Objective metric")
    table.add_column("Direction")
    table.add_column("Description", max_width=52)

    for name, info in _DOMAIN_INFO.items():
        table.add_row(
            name,
            info["objective"],
            info["direction"].value,
            info["desc"][:51],
        )

    console.print()
    console.print(table)


@app.command("info")
def cmd_info(domain: str = typer.Argument(..., help="Optimizer domain")):
    """Describe a domain's objective, metrics, and constraints."""
    if domain not in _DOMAIN_INFO:
        console.print(f"[red]Unknown domain '{domain}'. Run [bold]di list[/bold] to see available domains.[/red]")
        raise typer.Exit(1)

    info = _DOMAIN_INFO[domain]
    console.print()
    console.print(Panel(
        f"[bold blue]{domain.upper()}[/bold blue]\n\n"
        f"{info['desc']}\n\n"
        f"[dim]Metrics:[/dim]  {', '.join(info['metrics'])}\n"
        f"[dim]Default:[/dim]  objective={info['objective']}  direction={info['direction'].value}",
        border_style="blue",
        padding=(1, 2),
    ))


@app.command("run")
def cmd_run(
    domain: str = typer.Argument(..., help="Optimizer domain (collateral, money_market, financing)"),
    portfolio: str = typer.Option("PORT_001", "--portfolio", "-p", help="Portfolio identifier"),
    objective: Optional[str] = typer.Option(None, "--objective", "-o", help="Objective metric (default: domain's standard metric)"),
    scenario: Optional[str] = typer.Option(None, "--scenario", "-s", help="Scenario preset(s): stress, downside, inventory (comma-separated)"),
    seed: int = typer.Option(42, "--seed", help="RNG seed for simulated data"),
    mode: str = typer.Option("recommendation", "--mode", "-m", help="Execution mode: explain, scenario_analysis, recommendation"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full explanation text"),
    output: Optional[str] = typer.Option(None, "--output", "-O", help="Write output file: result.json | allocs.csv | report.html"),
    data: Optional[str] = typer.Option(
        None, "--data", "-d",
        help="JSON file with a 'data_source' config to load real data (CSV) instead of simulated",
    ),
):
    """Run an optimization for a domain and print structured results."""
    if domain not in _DOMAIN_INFO:
        console.print(f"[red]Unknown domain '{domain}'. Run [bold]di list[/bold] to see available domains.[/red]")
        raise typer.Exit(1)

    info = _DOMAIN_INFO[domain]
    metric = objective or info["objective"]
    direction = info["direction"]
    ctx = {**info["default_context"], "seed": seed}

    if data:
        ctx = {**ctx, **_load_data_source(data)}

    # Build scenario list
    scenarios = []
    if scenario:
        for name in scenario.split(","):
            name = name.strip()
            presets = _SCENARIO_PRESETS.get(name, {})
            overrides = presets.get(domain, {})
            scenarios.append(Scenario(
                name=name,
                scenario_type=ScenarioType.STRESS if "stress" in name else ScenarioType.DOWNSIDE,
                parameter_overrides=overrides,
            ))

    try:
        exec_mode = ExecutionMode(mode)
    except ValueError:
        console.print(f"[red]Unknown mode '{mode}'. Valid: explain, scenario_analysis, recommendation, stage, execute[/red]")
        raise typer.Exit(1)

    req = OptimizationRequest(
        domain=domain,
        portfolio_id=portfolio,
        objective=Objective(
            name=f"{direction.value}_{metric}",
            direction=direction,
            metric=metric,
        ),
        scenarios=scenarios,
        execution_mode=exec_mode,
        context=ctx,
        requestor="cli",
    )

    orch, audit = _build_registry()

    with console.status(f"[dim]Solving {domain}…[/dim]", spinner="dots"):
        result = orch.run(req)

    _print_result(domain, result, verbose)
    _write_output(output, result, req)


@app.command("ingest")
def cmd_ingest(
    pdf: str = typer.Argument(..., help="Path to a PDF brief describing the optimization"),
    backend: str = typer.Option(
        "auto", "--backend", "-b",
        help="Extraction backend: auto | llm | heuristic (auto uses LLM when ANTHROPIC_API_KEY is set)",
    ),
    seed: int = typer.Option(42, "--seed", help="RNG seed for simulated data"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full explanation text"),
    show_extraction: bool = typer.Option(
        True, "--show-extraction/--no-show-extraction",
        help="Print what the intake agent understood before solving",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Only parse the PDF into a request; do not solve",
    ),
    output: Optional[str] = typer.Option(None, "--output", "-O", help="Write output file: result.json | allocs.csv | report.html"),
):
    """Ingest a PDF brief into an OptimizationRequest and route it through the orchestrator."""
    from decision_intelligence.ingestion import IngestionError, ingest_pdf, llm_available

    path = Path(pdf)
    if not path.exists():
        console.print(f"[red]PDF not found: {path}[/red]")
        raise typer.Exit(1)

    if backend not in ("auto", "llm", "heuristic"):
        console.print(f"[red]Unknown backend '{backend}'. Valid: auto, llm, heuristic[/red]")
        raise typer.Exit(1)

    chosen = backend
    if chosen == "auto":
        chosen = "llm" if llm_available() else "heuristic"
    elif chosen == "llm" and not llm_available():
        console.print(
            "[red]LLM backend requested but unavailable.[/red] "
            "Set [bold]ANTHROPIC_API_KEY[/bold] and install the extra "
            "([bold]pip install -e '.[ingest]'[/bold]), or use "
            "[bold]--backend heuristic[/bold] for the offline parser."
        )
        raise typer.Exit(1)

    label = {
        "llm": "Claude (native PDF, claude-opus-4-8)",
        "heuristic": "offline heuristic (pypdf + rules)",
    }[chosen]

    console.print()
    console.print(Panel(
        f"[bold blue]PDF INGESTION[/bold blue]\n\n"
        f"[dim]Source:[/dim]  {path.name}\n"
        f"[dim]Backend:[/dim] {label}",
        border_style="blue",
        padding=(1, 2),
    ))

    try:
        with console.status(f"[dim]Reading {path.name}…[/dim]", spinner="dots"):
            req, extracted = ingest_pdf(path, backend=chosen, seed=seed)
    except IngestionError as exc:
        console.print(f"[red]Ingestion failed: {exc}[/red]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Ingestion error: {exc}[/red]")
        raise typer.Exit(1)

    if show_extraction:
        _print_extraction(req, extracted)

    if dry_run:
        console.print("[dim]--dry-run: parsed request only, not solving.[/dim]\n")
        return

    orch, audit = _build_registry()
    with console.status(f"[dim]Solving {req.domain}…[/dim]", spinner="dots"):
        result = orch.run(req)

    _print_result(req.domain, result, verbose)
    _write_output(output, result, req)


def _print_extraction(req, extracted):
    """Show what the intake agent recovered from the document."""
    console.print("[bold blue]  INTAKE AGENT — EXTRACTED REQUEST[/bold blue]")
    console.print(
        f"  [dim]domain[/dim]       [cyan]{req.domain}[/cyan]   "
        f"[dim]portfolio[/dim] {req.portfolio_id}   "
        f"[dim]requestor[/dim] {req.requestor}"
    )
    console.print(
        f"  [dim]objective[/dim]    {req.objective.direction.value} "
        f"[yellow]{req.objective.metric}[/yellow]   "
        f"[dim]mode[/dim] {req.execution_mode.value}"
    )

    if req.constraints:
        table = Table(box=box.SIMPLE, show_header=True, header_style="blue")
        table.add_column("Constraint", style="white")
        table.add_column("Type", style="dim")
        table.add_column("Parameters", style="magenta")
        for c in req.constraints:
            params = ", ".join(f"{k}={v}" for k, v in c.parameters.items()) or "—"
            table.add_row(c.name, c.constraint_type.value, params)
        console.print(table)

    if req.scenarios:
        console.print("[bold blue]  SCENARIOS DETECTED[/bold blue]")
        for s in req.scenarios:
            ov = ", ".join(f"{k}={v}" for k, v in s.parameter_overrides.items()) or "—"
            console.print(f"  [white]{s.name}[/white] [dim]({s.scenario_type.value})[/dim]  [magenta]{ov}[/magenta]")
        console.print()


def _print_result(domain: str, result, verbose: bool):
    console.print()

    # ── Status panel ──
    status_color = "green" if result.status == SolveStatus.OPTIMAL else "red"
    status_label = result.status.value.upper()
    imp_sign = "+" if result.improvement >= 0 else ""
    console.print(Panel(
        f"[bold]{domain.upper().replace('_', ' ')} OPTIMIZER[/bold]\n"
        f"[{status_color}]{status_label}[/{status_color}]   "
        f"obj [yellow]{result.objective_value:,.4f}[/yellow]   "
        f"base [dim]{result.baseline_value:,.4f}[/dim]   "
        f"impr [{'green' if result.improvement >= 0 else 'red'}]"
        f"{imp_sign}{result.improvement_pct:.2f}%[/{'green' if result.improvement >= 0 else 'red'}]",
        border_style=status_color,
        padding=(0, 1),
    ))

    if result.status != SolveStatus.OPTIMAL:
        console.print(f"[red]{result.explanation}[/red]")
        return

    # ── Progress bar ──
    frac = min(1.0, result.improvement_pct / 100)
    bar_str = _bar(frac, 32)
    filled = round(frac * 32)
    colored_bar = (
        f"[green]{'█' * max(0,filled-1)}{'▓' if filled else ''}[/green]"
        f"[dim]{'░' * (32-filled)}[/dim]"
    )
    console.print(f"  {colored_bar}  [yellow]{result.improvement_pct:.1f}%[/yellow]")
    console.print()

    # ── Allocations ──
    if result.allocations:
        table = Table(box=box.SIMPLE, show_header=True, header_style="blue")
        table.add_column("Asset / Source", style="white", max_width=36)
        table.add_column("Value", justify="right", style="yellow")
        table.add_column("", min_width=16)
        table.add_column("Fraction", justify="right")

        for a in sorted(result.allocations, key=lambda x: -x.allocated_value):
            b = _bar(a.allocated_fraction, 14)
            filled = round(a.allocated_fraction * 14)
            bfmt = (
                f"[yellow]{'█' * max(0,filled-1)}{'▓' if filled else ''}[/yellow]"
                f"[dim]{'░' * (14-filled)}[/dim]"
            )
            val_str = (
                f"${a.allocated_value/1e6:.1f}M"
                if a.allocated_value >= 1e6
                else f"${a.allocated_value:,.0f}"
            )
            table.add_row(a.label[:35], val_str, bfmt, f"{a.allocated_fraction:.1%}")

        console.print("[bold blue]  ALLOCATIONS[/bold blue]")
        console.print(table)

    # ── Binding constraints ──
    if result.binding_constraints:
        bc_str = "  [dim]·[/dim]  ".join(f"[dim]{b}[/dim]" for b in result.binding_constraints)
        console.print("[bold blue]  BINDING CONSTRAINTS[/bold blue]")
        console.print(f"  {bc_str}")
        console.print()

    # ── Sensitivity ──
    if result.sensitivities:
        table = Table(box=box.SIMPLE, show_header=True, header_style="blue")
        table.add_column("Parameter", max_width=30)
        table.add_column("Shadow Price", justify="right", style="magenta")
        table.add_column("Note", max_width=50, style="dim")

        for s in result.sensitivities[:5]:
            table.add_row(s.parameter, f"{s.shadow_price:.4f}", s.interpretation[:49])

        console.print("[bold blue]  SENSITIVITY[/bold blue]")
        console.print(table)

    # ── Explanation ──
    if verbose and result.explanation:
        console.print("[bold blue]  EXPLANATION[/bold blue]")
        console.print(f"  [dim]{result.explanation}[/dim]")
        console.print()

    # ── Validation ──
    if not result.validation.passed:
        console.print("[bold red]  CONSTRAINT VIOLATIONS[/bold red]")
        for v in result.validation.violations:
            console.print(f"  [red]✗[/red] {v}")
        console.print()
    else:
        console.print("[green]  ✓ solution validated — all constraints satisfied[/green]")

    # ── Scenarios ──
    if result.scenario_results:
        console.print()
        console.print("[bold blue]  SCENARIOS[/bold blue]")
        table = Table(box=box.SIMPLE, show_header=True, header_style="blue")
        table.add_column("Scenario", style="white")
        table.add_column("Objective", justify="right", style="yellow")
        table.add_column("Δ vs Base", justify="right")
        table.add_column("Impr %", justify="right")

        for name, sr in result.scenario_results.items():
            delta = sr.objective_value - result.objective_value
            sign = "+" if delta >= 0 else ""
            color = "red" if delta > 0 else "green"
            table.add_row(
                name,
                f"{sr.objective_value:,.2f}",
                f"[{color}]{sign}{delta:,.2f}[/{color}]",
                f"{sr.improvement_pct:.1f}%",
            )
        console.print(table)

    console.print()


def _load_data_source(data: str) -> dict:
    """Load a JSON file describing the data source into a context fragment.

    The file may be either the bare data_source dict
    (``{"type": "csv", "funds": "..."}``) or a wrapper
    (``{"data_source": {...}, "total_cash": ...}``). Returns a dict to merge
    into request.context.
    """
    path = Path(data)
    if not path.exists():
        console.print(f"[red]Data config not found: {path}[/red]")
        raise typer.Exit(1)
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid JSON in {path}: {exc}[/red]")
        raise typer.Exit(1)

    if "data_source" in payload:
        return payload  # already a context fragment
    if "type" in payload:
        return {"data_source": payload}
    console.print(
        f"[red]{path} must contain a 'data_source' object or a bare "
        "source dict with a 'type' key.[/red]"
    )
    raise typer.Exit(1)


def _write_output(output: str | None, result, request) -> None:
    if not output:
        return

    path = Path(output)
    ext = path.suffix.lower()

    try:
        if ext == ".json":
            export_json(result, path)
            console.print(f"[dim]JSON →[/dim] [cyan]{path}[/cyan]")

        elif ext == ".csv":
            export_csv(result, path)
            console.print(f"[dim]CSV  →[/dim] [cyan]{path}[/cyan]")

        elif ext in (".html", ".htm"):
            generate_report(result, request, path)
            console.print(f"[dim]HTML →[/dim] [cyan]{path}[/cyan]")

        else:
            console.print(
                f"[yellow]Unknown extension '{ext}'. "
                "Use .json, .csv, or .html[/yellow]"
            )
    except Exception as exc:
        console.print(f"[red]Export failed: {exc}[/red]")
        raise typer.Exit(1)


def main():
    app()


if __name__ == "__main__":
    main()
