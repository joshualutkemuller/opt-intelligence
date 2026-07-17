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
    from rich.prompt import Prompt
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
from decision_intelligence.contracts.approvals import ApprovalStatus
from decision_intelligence.chat import ChatSession
from decision_intelligence.governance import (
    ApprovalDecision,
    ApprovalPolicy,
    ApprovalStore,
    GovernanceController,
)
from decision_intelligence.governance.audit import AuditLog
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    AssetAllocationMVOOptimizer,
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
    "asset_allocation": {
        "desc": "Maximize mean-variance utility across asset classes subject to weight limits and optional target return.",
        "objective": "utility",
        "direction": ObjectiveDirection.MAXIMIZE,
        "metrics": ["utility", "risk_adjusted_return", "sharpe", "volatility"],
        "default_context": {
            "seed": 42,
            "portfolio_notional": 100_000_000,
            "risk_aversion": 3.0,
            "target_return": None,
            "problem_type": "qp",
        },
    },
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
        "asset_allocation": {
            "equity_return_shift": -0.025,
            "volatility_scale": 1.35,
            "min_cash_weight": 0.05,
        },
    },
    "credit_stress": {
        "collateral":   {"obligation_scale": 1.3},
        "money_market": {"daily_liquidity_req": 0.45, "yield_shift": 0.92},
        "financing":    {"spread_shift": 1.5, "capacity_scale": 0.6},
        "asset_allocation": {
            "equity_return_shift": -0.035,
            "bond_return_shift": -0.005,
            "volatility_scale": 1.50,
            "min_cash_weight": 0.06,
        },
    },
    "downside": {
        "collateral":   {"inventory_scale": 0.7},
        "money_market": {"yield_shift": 0.9},
        "financing":    {"spread_shift": 1.2, "capacity_scale": 0.8},
        "asset_allocation": {"return_shift": -0.01, "volatility_scale": 1.20},
    },
    "inventory": {
        "collateral":   {"inventory_scale": 0.7},
        "money_market": {},
        "financing":    {},
        "asset_allocation": {},
    },
}

_DOMAIN_ALIASES = {
    "collateral": "collateral",
    "collateral optimizer": "collateral",
    "money_market": "money_market",
    "money market": "money_market",
    "cash": "money_market",
    "liquidity": "money_market",
    "financing": "financing",
    "funding": "financing",
    "repo": "financing",
    "asset allocation": "asset_allocation",
    "asset_allocation": "asset_allocation",
    "allocation": "asset_allocation",
    "mvo": "asset_allocation",
    "portfolio": "asset_allocation",
}


def _build_registry() -> tuple[OptimizationOrchestrator, AuditLog]:
    audit = AuditLog()
    reg = OptimizerRegistry()
    reg.register(AssetAllocationMVOOptimizer())
    reg.register(CollateralOptimizer())
    reg.register(MoneyMarketOptimizer())
    reg.register(FinancingOptimizer())
    governance = GovernanceController(ApprovalPolicy(), ApprovalStore(), audit)
    return OptimizationOrchestrator(reg, audit, governance), audit


def _bar(frac: float, width: int = 24) -> str:
    frac = max(0.0, min(1.0, frac))
    filled = round(frac * width)
    empty = width - filled
    return "█" * max(0, filled - 1) + ("▓" if filled else "") + "░" * empty


def _detect_domain(text: str) -> str | None:
    normalized = text.lower().replace("-", " ").replace("_", " ")
    for alias, domain in sorted(_DOMAIN_ALIASES.items(), key=lambda item: -len(item[0])):
        if alias.replace("_", " ") in normalized:
            return domain
    return None


def _detect_scenarios(text: str) -> list[str]:
    normalized = text.lower().replace("-", " ")
    scenarios: list[str] = []

    if "credit" in normalized and "stress" in normalized:
        scenarios.append("credit_stress")
    elif "stress" in normalized or "liquidity shock" in normalized:
        scenarios.append("stress")

    if "downside" in normalized:
        scenarios.append("downside")
    if "inventory" in normalized or "squeeze" in normalized:
        scenarios.append("inventory")

    return scenarios


def _extract_pdf_path(text: str) -> str:
    for token in text.split():
        cleaned = token.strip("'\".,:;()[]")
        if cleaned.lower().endswith(".pdf"):
            return cleaned
    return "examples/sample_brief.pdf"


def _print_chat_help() -> None:
    console.print(Panel(
        "[bold blue]CHAT DEMO[/bold blue]\n\n"
        "Guided workflows:\n"
        "  Optimize a multi-asset allocation with MVO\n"
        "  I want to optimize money market cash\n"
        "  Help me source financing\n"
        "  Guide a collateral optimization\n\n"
        "Quick commands:\n"
        "Try prompts like:\n"
        "  list domains\n"
        "  optimize asset allocation under stress\n"
        "  tell me about collateral\n"
        "  optimize money market under stress\n"
        "  run financing with credit stress\n"
        "  parse the sample PDF\n"
        "  ingest examples/sample_brief.pdf and solve\n\n"
        "Type [bold]exit[/bold] to leave.",
        border_style="blue",
        padding=(1, 2),
    ))


def _run_guided_chat_turn(session: ChatSession, text: str) -> bool:
    response = session.reply(text)
    console.print("[bold blue]assistant[/bold blue] ", end="")
    console.print(response.message, markup=False)

    if response.request is not None:
        orch, audit = _build_registry()
        with console.status(f"[dim]Solving {response.request.domain}…[/dim]", spinner="dots"):
            result = orch.run(response.request)
        _print_result(response.request.domain, result, verbose=False)

    return not response.should_exit


def _chat_turn(text: str, seed: int, portfolio: str) -> bool:
    prompt = text.strip()
    normalized = prompt.lower()

    if not prompt:
        return True
    if normalized in {"exit", "quit", "q", "bye"}:
        console.print("[dim]Leaving chat demo.[/dim]")
        return False
    if normalized in {"help", "?", "examples"}:
        _print_chat_help()
        return True

    if "list" in normalized or "domains" in normalized or "capabilities" in normalized:
        console.print("[bold blue]assistant[/bold blue] I found the registered optimizer domains.")
        cmd_list()
        return True

    if "pdf" in normalized or "brief" in normalized or "ingest" in normalized:
        pdf = _extract_pdf_path(prompt)
        dry_run = "dry" in normalized or ("parse" in normalized and "solve" not in normalized)
        action = "parse only" if dry_run else "parse and solve"
        console.print(
            f"[bold blue]assistant[/bold blue] I will {action} "
            f"[cyan]{pdf}[/cyan] using the offline heuristic intake agent."
        )
        cmd_ingest(
            pdf=pdf,
            backend="heuristic",
            seed=seed,
            verbose=False,
            show_extraction=True,
            dry_run=dry_run,
            solver="scipy",
            problem_type="lp",
            solver_method=None,
            output=None,
        )
        return True

    domain = _detect_domain(prompt)
    if not domain:
        console.print(
            "[bold blue]assistant[/bold blue] I can route asset allocation, "
            "collateral, money market, or financing requests. Type [bold]help[/bold] "
            "for examples."
        )
        return True

    if "info" in normalized or "about" in normalized or "describe" in normalized:
        console.print(f"[bold blue]assistant[/bold blue] Here is the domain profile for [cyan]{domain}[/cyan].")
        cmd_info(domain)
        return True

    scenarios = _detect_scenarios(prompt)
    scenario_arg = ",".join(scenarios) if scenarios else None
    verbose = "explain" in normalized or "why" in normalized
    mode = "scenario_analysis" if scenario_arg else "recommendation"

    console.print(
        "[bold blue]assistant[/bold blue] Parsed request: "
        f"domain=[cyan]{domain}[/cyan], "
        f"portfolio=[cyan]{portfolio}[/cyan], "
        f"mode=[cyan]{mode}[/cyan], "
        f"scenarios=[cyan]{scenario_arg or 'none'}[/cyan], "
        f"seed=[cyan]{seed}[/cyan]."
    )
    cmd_run(
        domain=domain,
        portfolio=portfolio,
        objective=None,
        scenario=scenario_arg,
        seed=seed,
        mode=mode,
        verbose=verbose,
        output=None,
        solver="scipy",
        problem_type="lp",
        solver_method=None,
        data=None,
        approve_as=None,
        reject=False,
        reason="",
    )
    return True


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
    domain: str = typer.Argument(
        ...,
        help="Optimizer domain (asset_allocation, collateral, money_market, financing)",
    ),
    portfolio: str = typer.Option("PORT_001", "--portfolio", "-p", help="Portfolio identifier"),
    objective: Optional[str] = typer.Option(None, "--objective", "-o", help="Objective metric (default: domain's standard metric)"),
    scenario: Optional[str] = typer.Option(None, "--scenario", "-s", help="Scenario preset(s): stress, downside, inventory (comma-separated)"),
    seed: int = typer.Option(42, "--seed", help="RNG seed for simulated data"),
    mode: str = typer.Option("recommendation", "--mode", "-m", help="Execution mode: explain, scenario_analysis, recommendation"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full explanation text"),
    output: Optional[str] = typer.Option(None, "--output", "-O", help="Write output file: result.json | allocs.csv | report.html"),
    solver: str = typer.Option("scipy", "--solver", help="Solver backend: scipy | cvxpy"),
    problem_type: str = typer.Option("lp", "--problem-type", help="Problem type: lp | milp | qp | conic"),
    solver_method: Optional[str] = typer.Option(
        None, "--solver-method", help="Backend-specific solver method override",
    ),
    data: Optional[str] = typer.Option(
        None, "--data", "-d",
        help="JSON file with a 'data_source' config to load real data (CSV) instead of simulated",
    ),
    approve_as: Optional[str] = typer.Option(
        None, "--approve-as",
        help="Approver name — grants approval for gated modes (stage, execute) in one shot",
    ),
    reject: bool = typer.Option(
        False, "--reject", help="Reject the gated action (use with --approve-as as the approver)",
    ),
    reason: str = typer.Option("", "--reason", help="Reason recorded with an approve/reject decision"),
):
    """Run an optimization for a domain and print structured results."""
    if domain not in _DOMAIN_INFO:
        console.print(f"[red]Unknown domain '{domain}'. Run [bold]di list[/bold] to see available domains.[/red]")
        raise typer.Exit(1)

    info = _DOMAIN_INFO[domain]
    metric = objective or info["objective"]
    direction = info["direction"]
    ctx = {
        **info["default_context"],
        "seed": seed,
        "solver_backend": solver,
        "problem_type": problem_type,
    }
    if solver_method:
        ctx["solver_method"] = solver_method

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

    approval = None
    if approve_as:
        approval = ApprovalDecision(approver=approve_as, granted=not reject, reason=reason)

    with console.status(f"[dim]Solving {domain}…[/dim]", spinner="dots"):
        result = orch.run(req, approval=approval)

    _print_result(domain, result, verbose)
    _write_output(output, result, req)


@app.command("chat")
def cmd_chat(
    seed: int = typer.Option(42, "--seed", help="RNG seed for simulated data"),
    portfolio: str = typer.Option("PORT_001", "--portfolio", "-p", help="Portfolio identifier"),
    prompt: Optional[str] = typer.Option(
        None,
        "--prompt",
        help="Run a single chat prompt and exit; useful for scripted demos.",
    ),
):
    """Start a deterministic chat-style demo over the optimization CLI."""
    if prompt:
        _chat_turn(prompt, seed=seed, portfolio=portfolio)
        return

    session = ChatSession(seed=seed, default_portfolio=portfolio)
    _print_chat_help()
    while True:
        try:
            text = Prompt.ask("[bold cyan]you[/bold cyan]")
        except (EOFError, KeyboardInterrupt):
            console.print()
            console.print("[dim]Leaving chat demo.[/dim]")
            return

        normalized = text.strip().lower()
        domain = _detect_domain(text)
        should_use_quick = (
            not session.active
            and (
                normalized in {"help", "?", "examples", "exit", "quit", "q", "bye"}
                or "list" in normalized
                or "domains" in normalized
                or "capabilities" in normalized
                or "pdf" in normalized
                or "brief" in normalized
                or "ingest" in normalized
                or (
                    domain is not None
                    and (
                        "info" in normalized
                        or "about" in normalized
                        or "describe" in normalized
                    )
                )
            )
        )

        if should_use_quick:
            keep_going = _chat_turn(text, seed=seed, portfolio=portfolio)
        else:
            keep_going = _run_guided_chat_turn(session, text)

        if not keep_going:
            return


@app.command("ingest")
def cmd_ingest(
    pdf: str = typer.Argument(..., help="Path to a PDF brief describing the optimization"),
    backend: str = typer.Option(
        "auto", "--backend", "-b",
        help="Extraction backend: auto | llm | heuristic (auto uses an LLM provider when configured)",
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider",
        help="LLM provider: anthropic | openai | <registered> (default: DI_LLM_PROVIDER / auto-detect)",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="Model id override (default: DI_LLM_MODEL / provider default)",
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
    solver: str = typer.Option("scipy", "--solver", help="Solver backend: scipy | cvxpy"),
    problem_type: str = typer.Option("lp", "--problem-type", help="Problem type: lp | milp | qp | conic"),
    solver_method: Optional[str] = typer.Option(
        None, "--solver-method", help="Backend-specific solver method override",
    ),
    output: Optional[str] = typer.Option(None, "--output", "-O", help="Write output file: result.json | allocs.csv | report.html"),
):
    """Ingest a PDF brief into an OptimizationRequest and route it through the orchestrator."""
    from decision_intelligence.ingestion import IngestionError, ingest_pdf, llm_available
    from decision_intelligence.llm import LLMConfigError, resolve_provider

    path = Path(pdf)
    if not path.exists():
        console.print(f"[red]PDF not found: {path}[/red]")
        raise typer.Exit(1)

    if backend not in ("auto", "llm", "heuristic"):
        console.print(f"[red]Unknown backend '{backend}'. Valid: auto, llm, heuristic[/red]")
        raise typer.Exit(1)

    # Resolve an LLM provider if one is requested / configured.
    llm_provider = None
    want_llm = backend == "llm" or (backend == "auto" and (provider or llm_available()))
    if want_llm:
        try:
            llm_provider = resolve_provider(provider, model=model)
        except LLMConfigError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

    chosen = backend
    if chosen == "auto":
        chosen = "llm" if llm_provider is not None else "heuristic"
    elif chosen == "llm" and llm_provider is None:
        console.print(
            "[red]LLM backend requested but no provider is configured.[/red] "
            "Set [bold]DI_LLM_PROVIDER[/bold] (+ credentials / [bold]DI_LLM_BASE_URL[/bold] "
            "for local models) and install the extra "
            "([bold]pip install -e '.[ingest]'[/bold]), or use "
            "[bold]--backend heuristic[/bold] for the offline parser."
        )
        raise typer.Exit(1)

    if chosen == "llm":
        native = "native PDF" if llm_provider.supports_native_pdf else "text"
        label = f"LLM · {llm_provider.name} ({llm_provider.model}, {native})"
    else:
        label = "offline heuristic (pypdf + rules)"

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
            req, extracted = ingest_pdf(path, backend=chosen, seed=seed, provider=llm_provider)
    except IngestionError as exc:
        console.print(f"[red]Ingestion failed: {exc}[/red]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]Ingestion error: {exc}[/red]")
        raise typer.Exit(1)

    if show_extraction:
        _print_extraction(req, extracted)

    solver_context = {
        **req.context,
        "solver_backend": solver,
        "problem_type": problem_type,
    }
    if solver_method:
        solver_context["solver_method"] = solver_method
    req = req.model_copy(update={"context": solver_context})

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


_GOV_STYLE = {
    ApprovalStatus.NOT_REQUIRED: ("green", "✓", "auto-allowed"),
    ApprovalStatus.PENDING: ("yellow", "⏳", "APPROVAL REQUIRED"),
    ApprovalStatus.APPROVED: ("green", "✓", "APPROVED"),
    ApprovalStatus.REJECTED: ("red", "✗", "REJECTED"),
}


def _print_governance(gov):
    """Render the execution-mode governance decision, if present."""
    if gov is None:
        return

    color, glyph, label = _GOV_STYLE.get(gov.status, ("white", "•", gov.status.value))
    line = (
        f"[{color}]{glyph} GOVERNANCE[/{color}]  "
        f"mode [cyan]{gov.execution_mode}[/cyan] (tier {gov.tier})  "
        f"action [white]{gov.action}[/white]  "
        f"→ [{color}]{label}[/{color}]"
    )
    console.print(f"  {line}")

    if gov.status == ApprovalStatus.PENDING:
        console.print(
            f"  [dim]Action withheld. Approve with[/dim] "
            f"[bold]--approve-as <name>[/bold]  "
            f"[dim](approval_id: {gov.approval_id})[/dim]"
        )
    elif gov.status == ApprovalStatus.APPROVED:
        performed = "performed" if gov.action_performed else "not performed"
        console.print(
            f"  [dim]{gov.action.capitalize()} {performed} · "
            f"approver: {gov.approver}"
            + (f" · {gov.reason}" if gov.reason else "")
            + "[/dim]"
        )
    elif gov.status == ApprovalStatus.REJECTED:
        console.print(
            f"  [dim]Action withheld · approver: {gov.approver}"
            + (f" · {gov.reason}" if gov.reason else "")
            + "[/dim]"
        )
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

    _print_governance(result.governance)
    if result.solver_metadata:
        backend = result.solver_metadata.get("solver_backend", "unknown")
        problem_type = result.solver_metadata.get("problem_type", "unknown")
        solver_name = result.solver_metadata.get("solver", backend)
        console.print(
            f"  [dim]Solver[/dim] [cyan]{backend}/{problem_type}[/cyan] "
            f"[dim]({solver_name})[/dim]"
        )
        console.print()

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
