"""
End-to-end demo of the Decision Intelligence Platform.

Demonstrates:
  1. Building an OptimizationRequest for each domain
  2. Running through the orchestrator
  3. Printing structured results with explanation and sensitivities
  4. Running scenario analysis (stress test)

Run with:
    python examples/run_demo.py
"""

import sys
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from decision_intelligence.contracts import (
    Objective,
    ObjectiveDirection,
    OptimizationRequest,
    Scenario,
)
from decision_intelligence.contracts.scenarios import ScenarioType
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)

console = Console()


def build_orchestrator() -> OptimizationOrchestrator:
    reg = OptimizerRegistry()
    reg.register(CollateralOptimizer())
    reg.register(MoneyMarketOptimizer())
    reg.register(FinancingOptimizer())
    return OptimizationOrchestrator(reg)


def print_result(domain: str, result) -> None:
    status_color = "green" if result.status.value == "optimal" else "red"

    console.print(
        Panel(
            f"[bold]{domain.upper().replace('_', ' ')} OPTIMIZER[/bold]\n"
            f"Status: [{status_color}]{result.status.value}[/{status_color}]  |  "
            f"Objective: {result.objective_value:,.4f}  |  "
            f"Baseline: {result.baseline_value:,.4f}  |  "
            f"Improvement: [green]{result.improvement_pct:.2f}%[/green]",
            border_style="blue",
        )
    )

    if result.explanation:
        console.print("[dim]" + result.explanation + "[/dim]\n")

    if result.allocations:
        table = Table(title="Top Allocations", show_lines=False)
        table.add_column("Asset / Source", style="cyan", max_width=45)
        table.add_column("Allocated ($M)", justify="right")
        table.add_column("Fraction", justify="right")
        for a in sorted(result.allocations, key=lambda x: -x.allocated_value)[:8]:
            table.add_row(
                a.label[:44],
                f"{a.allocated_value/1e6:.2f}",
                f"{a.allocated_fraction:.2%}",
            )
        console.print(table)

    if result.sensitivities:
        table = Table(title="Sensitivity Analysis", show_lines=False)
        table.add_column("Parameter", style="yellow", max_width=40)
        table.add_column("Shadow Price", justify="right")
        table.add_column("Interpretation", max_width=60)
        for s in result.sensitivities[:4]:
            table.add_row(s.parameter, f"{s.shadow_price:.4f}", s.interpretation[:59])
        console.print(table)

    if result.scenario_results:
        console.print("\n[bold]Scenario Results:[/bold]")
        for name, sr in result.scenario_results.items():
            delta = sr.objective_value - result.objective_value
            console.print(
                f"  {name}: obj={sr.objective_value:,.4f}  Δ={delta:+,.4f}  "
                f"({sr.improvement_pct:.1f}% vs own baseline)"
            )

    console.print()


def run_collateral(orch: OptimizationOrchestrator) -> None:
    req = OptimizationRequest(
        domain="collateral",
        portfolio_id="COLL_PORT_001",
        objective=Objective(
            name="minimize_funding_cost",
            direction=ObjectiveDirection.MINIMIZE,
            metric="funding_cost",
        ),
        scenarios=[
            Scenario(
                name="stress_50pct",
                scenario_type=ScenarioType.STRESS,
                parameter_overrides={"obligation_scale": 1.5},
            ),
            Scenario(
                name="inventory_squeeze",
                scenario_type=ScenarioType.DOWNSIDE,
                parameter_overrides={"inventory_scale": 0.7},
            ),
        ],
        context={"seed": 42, "n_assets": 20},
        requestor="demo_user",
    )
    result = orch.run(req)
    print_result("collateral", result)


def run_money_market(orch: OptimizationOrchestrator) -> None:
    req = OptimizationRequest(
        domain="money_market",
        portfolio_id="MM_PORT_001",
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
        },
        requestor="demo_user",
    )
    result = orch.run(req)
    print_result("money_market", result)


def run_financing(orch: OptimizationOrchestrator) -> None:
    req = OptimizationRequest(
        domain="financing",
        portfolio_id="FIN_PORT_001",
        objective=Objective(
            name="minimize_funding_spread",
            direction=ObjectiveDirection.MINIMIZE,
            metric="funding_spread",
        ),
        scenarios=[
            Scenario(
                name="credit_stress",
                scenario_type=ScenarioType.STRESS,
                parameter_overrides={"spread_shift": 1.5, "capacity_scale": 0.6},
            ),
        ],
        context={
            "seed": 42,
            "n_counterparties": 10,
            "total_funding_need": 300_000_000,
        },
        requestor="demo_user",
    )
    result = orch.run(req)
    print_result("financing", result)


def main() -> None:
    console.rule("[bold blue]Decision Intelligence Platform — POC Demo[/bold blue]")
    console.print(
        "Simulated data. Real LP optimization (scipy/HiGHS). "
        "Swap data layers for production.\n"
    )

    orch = build_orchestrator()
    console.print(f"Registered domains: {orch.registry.list_domains()}\n")

    console.rule("1 / 3  Collateral Optimizer")
    run_collateral(orch)

    console.rule("2 / 3  Money Market Optimizer")
    run_money_market(orch)

    console.rule("3 / 3  Financing Optimizer")
    run_financing(orch)

    console.rule("[green]Demo Complete[/green]")
    audit_entries = orch.audit.all_entries()
    console.print(f"Audit log: {len(audit_entries)} entries recorded across all requests.")


if __name__ == "__main__":
    main()
