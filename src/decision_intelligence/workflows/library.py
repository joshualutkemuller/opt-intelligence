"""Reusable workflow builders for higher-level optimization demos."""

from __future__ import annotations

from typing import Any

from decision_intelligence.contracts import Objective, ObjectiveDirection, OptimizationRequest
from decision_intelligence.contracts.requests import ExecutionMode

from .types import WorkflowPlan, WorkflowStep

LIQUIDITY_STRESS_WORKFLOW_ID = "liquidity_stress_funding_workflow"


def build_liquidity_stress_funding_workflow(
    *,
    portfolio_id: str = "PORT_001",
    seed: int = 42,
    context: dict[str, Any] | None = None,
) -> WorkflowPlan:
    """Build a financing -> collateral -> money-market stress workflow."""

    overrides = dict(context or {})
    workflow_context = {
        "portfolio_id": portfolio_id,
        "seed": seed,
        "scenario": overrides.get("scenario", "stress"),
        "solver_backend": overrides.get("solver_backend", "scipy"),
        "problem_type": overrides.get("problem_type", "lp"),
    }

    financing_context = _domain_context(
        overrides,
        "financing",
        {
            "n_counterparties": 10,
            "total_funding_need": 300_000_000,
            "spread_shift": 1.5,
            "capacity_scale": 0.6,
        },
        workflow_context,
    )
    collateral_context = _domain_context(
        overrides,
        "collateral",
        {
            "n_assets": 20,
            "obligation_scale": 1.5,
            "concentration_limit": 0.60,
        },
        workflow_context,
    )
    money_market_context = _domain_context(
        overrides,
        "money_market",
        {
            "n_funds": 8,
            "total_cash": 500_000_000,
            "daily_liquidity_req": 0.40,
            "weekly_liquidity_req": 0.70,
            "max_prime_fraction": 0.40,
            "max_wam_days": 60,
        },
        workflow_context,
    )

    return WorkflowPlan(
        workflow_id=LIQUIDITY_STRESS_WORKFLOW_ID,
        name="Liquidity Stress Funding Workflow",
        description=(
            "Runs funding source, collateral allocation, and money-market "
            "allocation optimizers under a shared liquidity stress setup."
        ),
        context=workflow_context,
        steps=[
            WorkflowStep(
                step_id="financing_001",
                domain="financing",
                name="Stress funding source optimization",
                description="Identify the lowest-cost executable funding mix under stress.",
                request=_request(
                    domain="financing",
                    portfolio_id=portfolio_id,
                    direction=ObjectiveDirection.MINIMIZE,
                    metric="funding_spread",
                    context=financing_context,
                ),
            ),
            WorkflowStep(
                step_id="collateral_001",
                domain="collateral",
                name="Collateral coverage optimization",
                description="Allocate available collateral against stressed obligations.",
                depends_on=["financing_001"],
                request=_request(
                    domain="collateral",
                    portfolio_id=portfolio_id,
                    direction=ObjectiveDirection.MINIMIZE,
                    metric="funding_cost",
                    context=collateral_context,
                ),
            ),
            WorkflowStep(
                step_id="money_market_001",
                domain="money_market",
                name="Liquidity reserve allocation",
                description="Allocate cash reserves while meeting stressed liquidity needs.",
                depends_on=["financing_001", "collateral_001"],
                request=_request(
                    domain="money_market",
                    portfolio_id=portfolio_id,
                    direction=ObjectiveDirection.MAXIMIZE,
                    metric="yield",
                    context=money_market_context,
                ),
            ),
        ],
    )


def _domain_context(
    overrides: dict[str, Any],
    domain: str,
    defaults: dict[str, Any],
    workflow_context: dict[str, Any],
) -> dict[str, Any]:
    shared = {
        key: value
        for key, value in overrides.items()
        if key
        not in {
            "financing",
            "collateral",
            "money_market",
            "scenario",
        }
    }
    domain_overrides = overrides.get(domain, {})
    if domain_overrides is None:
        domain_overrides = {}
    if not isinstance(domain_overrides, dict):
        raise TypeError(f"context['{domain}'] must be a dict when provided.")

    return {
        **workflow_context,
        **defaults,
        **shared,
        **domain_overrides,
        "workflow_id": LIQUIDITY_STRESS_WORKFLOW_ID,
        "workflow_domain": domain,
    }


def _request(
    *,
    domain: str,
    portfolio_id: str,
    direction: ObjectiveDirection,
    metric: str,
    context: dict[str, Any],
) -> OptimizationRequest:
    return OptimizationRequest(
        domain=domain,
        portfolio_id=portfolio_id,
        objective=Objective(
            name=f"{direction.value}_{metric}",
            direction=direction,
            metric=metric,
        ),
        execution_mode=ExecutionMode.RECOMMENDATION,
        context=context,
        requestor="workflow",
    )
