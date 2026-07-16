"""
Focused solver-backend demo for the money-market optimizer.

Run with:
    python examples/run_solver_demo.py
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from decision_intelligence.contracts import Objective, ObjectiveDirection, OptimizationRequest
from decision_intelligence.contracts.results import OptimizationResult, SolveStatus
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import MoneyMarketOptimizer

console = Console(width=140)


def build_orchestrator() -> OptimizationOrchestrator:
    registry = OptimizerRegistry()
    registry.register(MoneyMarketOptimizer())
    return OptimizationOrchestrator(registry)


def build_request(label: str, context: dict[str, object]) -> OptimizationRequest:
    return OptimizationRequest(
        domain="money_market",
        portfolio_id=f"MM_SOLVER_DEMO_{label.upper()}",
        objective=Objective(
            name="maximize_yield",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="yield",
        ),
        context={
            "seed": 42,
            "n_funds": 8,
            "total_cash": 500_000_000,
            "daily_liquidity_req": 0.30,
            "weekly_liquidity_req": 0.60,
            "max_prime_fraction": 0.40,
            "max_wam_days": 60,
            "max_single_fund": 0.50,
            **context,
        },
        requestor="solver_demo",
    )


def format_top_allocations(result: OptimizationResult) -> str:
    top = sorted(result.allocations, key=lambda item: -item.allocated_fraction)[:3]
    return ", ".join(f"{item.label}: {item.allocated_fraction:.1%}" for item in top)


def render_results(results: list[tuple[str, OptimizationResult]]) -> None:
    table = Table(title="Money Market Solver Comparison", show_lines=False)
    table.add_column("Run", style="cyan")
    table.add_column("Status")
    table.add_column("Solver")
    table.add_column("Objective", justify="right")
    table.add_column("Improvement", justify="right")
    table.add_column("Funds Used", justify="right")
    table.add_column("Top Allocations", max_width=58)

    for label, result in results:
        solver = result.solver_metadata.get("solver_backend", "?")
        problem_type = result.solver_metadata.get("problem_type", "?")
        funds_used = result.solver_metadata.get("n_funds_used", len(result.allocations))
        status_style = "green" if result.status == SolveStatus.OPTIMAL else "red"
        table.add_row(
            label,
            f"[{status_style}]{result.status.value}[/{status_style}]",
            f"{solver}/{problem_type}",
            f"{result.objective_value:.4f}",
            f"{result.improvement_pct:.2f}%",
            str(funds_used),
            format_top_allocations(result),
        )

    console.print(table)


def main() -> None:
    orchestrator = build_orchestrator()
    requests = [
        (
            "SciPy LP",
            build_request("scipy_lp", {"solver_backend": "scipy", "problem_type": "lp"}),
        ),
        (
            "SciPy MILP",
            build_request(
                "scipy_milp",
                {
                    "solver_backend": "scipy",
                    "problem_type": "milp",
                    "max_funds": 3,
                    "min_allocation_fraction": 0.10,
                },
            ),
        ),
        (
            "CVXPY LP",
            build_request("cvxpy_lp", {"solver_backend": "cvxpy", "problem_type": "lp"}),
        ),
    ]

    results = [(label, orchestrator.run(request)) for label, request in requests]
    render_results(results)

    failed = [label for label, result in results if result.status != SolveStatus.OPTIMAL]
    if failed:
        raise SystemExit(f"Solver demo failed for: {', '.join(failed)}")


if __name__ == "__main__":
    main()
