"""
Presenter-ready proof-of-concept demo.

Run with:
    python examples/run_poc_video_demo.py

This script is intentionally deterministic. It walks through the strongest
terminal story for a video: guided chat intake, true MILP fund selection, and a
multi-step stress workflow with dependency propagation.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from decision_intelligence.chat import ChatSession
from decision_intelligence.contracts import Objective, ObjectiveDirection, OptimizationRequest
from decision_intelligence.contracts.results import OptimizationResult, SolveStatus
from decision_intelligence.governance import ApprovalPolicy, ApprovalStore, GovernanceController
from decision_intelligence.governance.audit import AuditLog
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    AssetAllocationMVOOptimizer,
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)
from decision_intelligence.workflows import (
    DEFAULT_DEMO_PRESET_DIR,
    DEFAULT_WORKFLOW_REGISTRY,
    SequentialWorkflowRunner,
    WorkflowResult,
    load_demo_preset,
)

console = Console(width=132)


def build_orchestrator() -> OptimizationOrchestrator:
    audit = AuditLog()
    registry = OptimizerRegistry()
    registry.register(AssetAllocationMVOOptimizer())
    registry.register(CollateralOptimizer())
    registry.register(MoneyMarketOptimizer())
    registry.register(FinancingOptimizer())
    governance = GovernanceController(ApprovalPolicy(), ApprovalStore(), audit)
    return OptimizationOrchestrator(registry, audit, governance)


def main() -> None:
    console.clear()
    _title()
    _act_1_guided_chat_milp()
    _act_2_solver_choice()
    _act_3_executive_workflow()
    _close()


def _title() -> None:
    console.rule("[bold blue]Decision Intelligence Platform POC[/bold blue]")
    console.print(
        Panel(
            "[bold]Video thesis[/bold]\n"
            "A user can describe a treasury optimization problem in plain language, "
            "the platform collects the missing facts, selects an optimization engine, "
            "runs deterministic math, validates the result, and explains a sequential "
            "workflow that links funding, collateral, and liquidity decisions.",
            title="Opening",
            border_style="blue",
        )
    )


def _act_1_guided_chat_milp() -> None:
    _section(
        "1. Guided Chat Intake",
        "Show that the agent turns a broad request into a structured optimization request.",
    )

    session = ChatSession(seed=42, default_portfolio="PORT_VIDEO_001")
    turns = [
        "optimize money market cash under stress with MILP fund selection",
        "PORT_VIDEO_001",
        "$500 million",
        "40%",
        "70%",
        "35%",
        "55",
        "50%",
        "3",
        "10%",
        "scipy",
        "milp",
        "yes",
    ]

    final_request: OptimizationRequest | None = None
    for text in turns:
        _user(text)
        response = session.reply(text)
        _agent(response.message)
        if response.request is not None:
            final_request = response.request

    if final_request is None:
        raise RuntimeError("Guided chat did not compile an OptimizationRequest.")

    _request_table(final_request)
    orchestrator = build_orchestrator()
    result = orchestrator.run(final_request)
    _money_market_result(result)


def _act_2_solver_choice() -> None:
    _section(
        "2. Solver Choice",
        "Show that solver backend and problem type are explicit inputs, not hidden code paths.",
    )

    orchestrator = build_orchestrator()
    requests = [
        _money_market_request(
            "SciPy LP",
            {
                "solver_backend": "scipy",
                "problem_type": "lp",
                "daily_liquidity_req": 0.30,
                "weekly_liquidity_req": 0.60,
                "max_prime_fraction": 0.40,
                "max_wam_days": 60,
            },
        ),
        _money_market_request(
            "SciPy MILP",
            {
                "solver_backend": "scipy",
                "problem_type": "milp",
                "daily_liquidity_req": 0.30,
                "weekly_liquidity_req": 0.60,
                "max_prime_fraction": 0.40,
                "max_wam_days": 60,
                "max_funds": 3,
                "min_allocation_fraction": 0.10,
            },
        ),
        _money_market_request(
            "CVXPY LP",
            {
                "solver_backend": "cvxpy",
                "problem_type": "lp",
                "daily_liquidity_req": 0.30,
                "weekly_liquidity_req": 0.60,
                "max_prime_fraction": 0.40,
                "max_wam_days": 60,
            },
        ),
    ]
    rows = [(label, orchestrator.run(request)) for label, request in requests]

    table = Table(title="Same business problem, selectable math engine", show_lines=False)
    table.add_column("Run", style="cyan")
    table.add_column("Status")
    table.add_column("Solver")
    table.add_column("Objective", justify="right")
    table.add_column("Improvement", justify="right")
    table.add_column("Funds Used", justify="right")
    table.add_column("Presenter note", max_width=50)
    for label, result in rows:
        meta = result.solver_metadata
        status_style = "green" if result.status == SolveStatus.OPTIMAL else "red"
        note = (
            "Binary fund-selection constraints are active."
            if meta.get("problem_type") == "milp"
            else "Continuous allocation benchmark."
        )
        table.add_row(
            label,
            f"[{status_style}]{result.status.value}[/{status_style}]",
            f"{meta.get('solver_backend', 'n/a')}/{meta.get('problem_type', 'n/a')}",
            f"{result.objective_value:.4f}",
            f"{result.improvement_pct:.2f}%",
            str(meta.get("n_funds_used", len(result.allocations))),
            note if result.status == SolveStatus.OPTIMAL else result.explanation[:48],
        )
    console.print(table)


def _act_3_executive_workflow() -> None:
    _section(
        "3. Executive Workflow",
        "This is the money shot: a sequential treasury stress workflow "
        "with dependency propagation.",
    )

    preset_path = DEFAULT_DEMO_PRESET_DIR / "institutional_csv_liquidity_stress.yaml"
    preset = load_demo_preset(preset_path)
    _preset_panel(preset_path, preset)

    plan = DEFAULT_WORKFLOW_REGISTRY.build(
        preset.workflow_id,
        portfolio_id=preset.portfolio_id,
        seed=preset.seed,
        context=preset.context,
    )

    plan_lines = []
    for index, step in enumerate(plan.steps, start=1):
        plan_lines.append(f"[bold]{index}. {step.name}[/bold] ({step.domain})")
        plan_lines.append(f"   {step.description or 'Run optimizer step.'}")
    console.print(Panel("\n".join(plan_lines), title="Workflow Plan", border_style="cyan"))

    result = SequentialWorkflowRunner(build_orchestrator()).run(plan)
    _workflow_timeline(result)
    _dependency_table(result)
    _workflow_explanation(result)
    _video_talking_points(preset.talking_points, preset.success_criteria)


def _money_market_request(label: str, context: dict[str, Any]) -> tuple[str, OptimizationRequest]:
    return (
        label,
        OptimizationRequest(
            domain="money_market",
            portfolio_id=f"PORT_VIDEO_{label.upper().replace(' ', '_')}",
            objective=Objective(
                name="maximize_yield",
                direction=ObjectiveDirection.MAXIMIZE,
                metric="yield",
            ),
            context={
                "seed": 42,
                "n_funds": 8,
                "total_cash": 500_000_000,
                "daily_liquidity_req": 0.40,
                "weekly_liquidity_req": 0.70,
                "max_prime_fraction": 0.35,
                "max_wam_days": 55,
                "max_single_fund": 0.50,
                **context,
            },
            requestor="video_demo",
        ),
    )


def _request_table(request: OptimizationRequest) -> None:
    table = Table(title="Compiled OptimizationRequest", show_lines=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("domain", request.domain)
    table.add_row("portfolio", request.portfolio_id)
    table.add_row("objective", f"{request.objective.direction.value} {request.objective.metric}")
    table.add_row("execution mode", request.execution_mode.value)
    table.add_row("scenarios", ", ".join(s.name for s in request.scenarios) or "none")
    for key in [
        "total_cash",
        "daily_liquidity_req",
        "weekly_liquidity_req",
        "max_prime_fraction",
        "max_wam_days",
        "max_funds",
        "min_allocation_fraction",
        "solver_backend",
        "problem_type",
    ]:
        if key in request.context:
            table.add_row(key, _format_value(request.context[key]))
    console.print(table)


def _money_market_result(result: OptimizationResult) -> None:
    meta = result.solver_metadata
    console.print(
        Panel(
            f"[bold green]{result.status.value.upper()}[/bold green]\n"
            f"Solver: {meta.get('solver_backend')}/{meta.get('problem_type')} "
            f"({meta.get('solver')})\n"
            f"Objective: {result.objective_value:.4f}% vs baseline "
            f"{result.baseline_value:.4f}%\n"
            f"Improvement: {result.improvement_pct:.2f}%\n"
            f"Selected funds: {meta.get('n_funds_used')} of max {meta.get('max_funds')}\n"
            f"Validation: {_validation_label(result)}",
            title="MILP Proof",
            border_style="green",
        )
    )

    table = Table(title="Selected Money-Market Funds", show_lines=False)
    table.add_column("Fund", style="cyan")
    table.add_column("Allocation", justify="right")
    table.add_column("Value", justify="right")
    table.add_column("Yield", justify="right")
    table.add_column("WAM", justify="right")
    for allocation in result.allocations:
        table.add_row(
            allocation.label,
            f"{allocation.allocated_fraction:.1%}",
            f"${allocation.allocated_value / 1_000_000:,.0f}M",
            f"{allocation.metadata.get('yield_7day', 0):.2f}%",
            f"{allocation.metadata.get('wam_days', 0):.0f}d",
        )
    console.print(table)


def _preset_panel(path: Path, preset: Any) -> None:
    console.print(
        Panel(
            f"[bold]{preset.name}[/bold]\n"
            f"Audience: {preset.audience}\n"
            f"Preset: {preset.preset_id}\n"
            f"Workflow: {preset.workflow_id}\n"
            f"Source: {path}",
            title="Demo Preset",
            border_style="blue",
        )
    )


def _workflow_timeline(result: WorkflowResult) -> None:
    table = Table(title="Sequential Workflow Result", show_lines=False)
    table.add_column("Step", style="cyan")
    table.add_column("Domain")
    table.add_column("Status")
    table.add_column("Objective", justify="right")
    table.add_column("Improvement", justify="right")
    table.add_column("Validation")
    table.add_column("Allocations", justify="right")

    for step in result.step_results:
        validation = step.result.validation_report
        table.add_row(
            step.name,
            step.domain,
            step.status,
            f"{step.result.objective_value:.4f}",
            f"{step.result.improvement_pct:.2f}%",
            validation.recommendation if validation else "ready",
            str(len(step.result.allocations)),
        )
    console.print(table)


def _dependency_table(result: WorkflowResult) -> None:
    changes = result.dependency_summary.get("context_changes", [])
    if not changes:
        console.print("[yellow]No dependency changes were applied.[/yellow]")
        return

    table = Table(title="Cross-Step Dependency Effects", show_lines=False)
    table.add_column("Source", style="cyan")
    table.add_column("Target")
    table.add_column("Context Key")
    table.add_column("Before", justify="right")
    table.add_column("After", justify="right")
    table.add_column("Why", max_width=54)
    for change in changes:
        table.add_row(
            str(change["source_step_id"]),
            str(change["target_step_id"]),
            str(change["target_context_key"]),
            _format_value(change["previous_value"]),
            _format_value(change["new_value"]),
            str(change["reason"]),
        )
    console.print(table)


def _workflow_explanation(result: WorkflowResult) -> None:
    report = result.explanation_report
    if report is None:
        return

    console.print(
        Panel(
            f"[bold]Summary[/bold]\n{report.summary}\n\n"
            f"[bold]Recommendation[/bold]\n{report.overall_recommendation}",
            title="Deterministic Workflow Explanation",
            border_style="green" if result.status == "complete" else "yellow",
        )
    )
    _bullet_panel("Key Drivers", report.key_drivers[:4], "cyan")
    _bullet_panel("Next Actions", report.next_actions[:4], "green")


def _video_talking_points(talking_points: Iterable[str], success_criteria: Iterable[str]) -> None:
    _bullet_panel("Say This On Camera", talking_points, "magenta")
    _bullet_panel("Call Out Success Criteria", success_criteria, "blue")


def _close() -> None:
    console.rule("[bold green]POC Complete[/bold green]")
    console.print(
        Panel(
            "Close the video by naming the architecture: deterministic optimizer core, "
            "agent-guided intake, pluggable solver layer, validation/governance, and "
            "sequential workflow orchestration. The output is repeatable, explainable, "
            "and demo-safe.",
            title="Closing Line",
            border_style="green",
        )
    )


def _section(title: str, proof: str) -> None:
    console.rule(f"[bold blue]{title}[/bold blue]")
    console.print(Panel(proof, title="Proof Point", border_style="blue"))


def _user(text: str) -> None:
    console.print(Text("you> ", style="bold cyan") + Text(text))


def _agent(message: str) -> None:
    console.print(Text("agent> ", style="bold blue") + Text(_compact(message)))


def _compact(message: str) -> str:
    lines = [line for line in message.splitlines() if line.strip()]
    if len(lines) <= 5:
        return "\n".join(lines)
    return "\n".join([*lines[:3], "...", *lines[-2:]])


def _bullet_panel(title: str, items: Iterable[str], style: str) -> None:
    text = "\n".join(f"- {item}" for item in items)
    console.print(Panel(text or "- none", title=title, border_style=style))


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int | float):
        number = float(value)
        if abs(number) >= 1_000_000:
            return f"${number / 1_000_000:,.0f}M"
        if 0 <= number <= 1:
            return f"{number:.0%}"
        return f"{number:g}"
    return str(value)


def _validation_label(result: OptimizationResult) -> str:
    report = result.validation_report
    if report is None:
        return "passed" if result.validation.passed else "review"
    return f"{report.recommendation} (risk score {report.risk_score:.2f})"


if __name__ == "__main__":
    main()
