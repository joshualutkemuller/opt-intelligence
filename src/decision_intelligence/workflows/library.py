"""Reusable workflow builders for higher-level optimization demos."""

from __future__ import annotations

from typing import Any

from decision_intelligence.contracts import Objective, ObjectiveDirection, OptimizationRequest
from decision_intelligence.contracts.requests import ExecutionMode

from .types import WorkflowDependencyRule, WorkflowPlan, WorkflowStep

LIQUIDITY_STRESS_WORKFLOW_ID = "liquidity_stress_funding_workflow"
FUNDING_CAPACITY_SHOCK_WORKFLOW_ID = "funding_capacity_shock"
COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID = "collateral_liquidity_review"


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
        LIQUIDITY_STRESS_WORKFLOW_ID,
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
        LIQUIDITY_STRESS_WORKFLOW_ID,
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
        LIQUIDITY_STRESS_WORKFLOW_ID,
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
                dependency_rules=[
                    WorkflowDependencyRule(
                        source_step_id="financing_001",
                        rule_type="funding_pressure_liquidity_buffer",
                        target_context_keys=[
                            "daily_liquidity_req",
                            "weekly_liquidity_req",
                        ],
                        description=(
                            "Raise liquidity requirements when financing capacity "
                            "or cost pressure is elevated."
                        ),
                    ),
                    WorkflowDependencyRule(
                        source_step_id="collateral_001",
                        rule_type="collateral_pressure_liquidity_buffer",
                        target_context_keys=[
                            "daily_liquidity_req",
                            "weekly_liquidity_req",
                        ],
                        description=(
                            "Raise liquidity requirements when collateral coverage "
                            "or inventory constraints are tight."
                        ),
                    ),
                ],
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


def build_funding_capacity_shock_workflow(
    *,
    portfolio_id: str = "PORT_001",
    seed: int = 42,
    context: dict[str, Any] | None = None,
) -> WorkflowPlan:
    """Build a financing -> money-market workflow for funding capacity shocks."""

    overrides = dict(context or {})
    workflow_context = _workflow_context(portfolio_id, seed, overrides, "capacity_shock")
    financing_context = _domain_context(
        overrides,
        "financing",
        FUNDING_CAPACITY_SHOCK_WORKFLOW_ID,
        {
            "n_counterparties": 10,
            "total_funding_need": 350_000_000,
            "spread_shift": 1.8,
            "capacity_scale": 0.45,
            "max_cp_concentration": 0.35,
        },
        workflow_context,
    )
    money_market_context = _domain_context(
        overrides,
        "money_market",
        FUNDING_CAPACITY_SHOCK_WORKFLOW_ID,
        {
            "n_funds": 8,
            "total_cash": 400_000_000,
            "daily_liquidity_req": 0.35,
            "weekly_liquidity_req": 0.65,
            "max_prime_fraction": 0.35,
            "max_wam_days": 55,
        },
        workflow_context,
    )

    return WorkflowPlan(
        workflow_id=FUNDING_CAPACITY_SHOCK_WORKFLOW_ID,
        name="Funding Capacity Shock",
        description=(
            "Runs stressed financing capacity first, then adjusts money-market "
            "liquidity reserves based on funding pressure."
        ),
        context=workflow_context,
        steps=[
            WorkflowStep(
                step_id="financing_001",
                domain="financing",
                name="Funding capacity shock optimization",
                description="Find executable funding under reduced capacity and wider spreads.",
                request=_request(
                    domain="financing",
                    portfolio_id=portfolio_id,
                    direction=ObjectiveDirection.MINIMIZE,
                    metric="funding_spread",
                    context=financing_context,
                ),
            ),
            WorkflowStep(
                step_id="money_market_001",
                domain="money_market",
                name="Liquidity reserve response",
                description="Rebalance liquidity reserves after the funding shock.",
                depends_on=["financing_001"],
                dependency_rules=[
                    WorkflowDependencyRule(
                        source_step_id="financing_001",
                        rule_type="funding_pressure_liquidity_buffer",
                        target_context_keys=[
                            "daily_liquidity_req",
                            "weekly_liquidity_req",
                        ],
                        description=(
                            "Raise liquidity requirements when financing capacity "
                            "or cost pressure is elevated."
                        ),
                    )
                ],
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


def build_collateral_liquidity_review_workflow(
    *,
    portfolio_id: str = "PORT_001",
    seed: int = 42,
    context: dict[str, Any] | None = None,
) -> WorkflowPlan:
    """Build a collateral -> money-market workflow for liquidity review."""

    overrides = dict(context or {})
    workflow_context = _workflow_context(portfolio_id, seed, overrides, "collateral_review")
    collateral_context = _domain_context(
        overrides,
        "collateral",
        COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID,
        {
            "n_assets": 20,
            "obligation_scale": 1.65,
            "concentration_limit": 0.55,
        },
        workflow_context,
    )
    money_market_context = _domain_context(
        overrides,
        "money_market",
        COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID,
        {
            "n_funds": 8,
            "total_cash": 450_000_000,
            "daily_liquidity_req": 0.35,
            "weekly_liquidity_req": 0.65,
            "max_prime_fraction": 0.40,
            "max_wam_days": 55,
        },
        workflow_context,
    )

    return WorkflowPlan(
        workflow_id=COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID,
        name="Collateral Liquidity Review",
        description=(
            "Runs collateral coverage analysis, then adjusts money-market liquidity "
            "requirements based on collateral pressure."
        ),
        context=workflow_context,
        steps=[
            WorkflowStep(
                step_id="collateral_001",
                domain="collateral",
                name="Collateral pressure optimization",
                description="Assess coverage under elevated collateral obligations.",
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
                name="Liquidity allocation review",
                description="Rebalance money-market liquidity after collateral review.",
                depends_on=["collateral_001"],
                dependency_rules=[
                    WorkflowDependencyRule(
                        source_step_id="collateral_001",
                        rule_type="collateral_pressure_liquidity_buffer",
                        target_context_keys=[
                            "daily_liquidity_req",
                            "weekly_liquidity_req",
                        ],
                        description=(
                            "Raise liquidity requirements when collateral coverage "
                            "or inventory constraints are tight."
                        ),
                    )
                ],
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


def _workflow_context(
    portfolio_id: str,
    seed: int,
    overrides: dict[str, Any],
    default_scenario: str,
) -> dict[str, Any]:
    return {
        "portfolio_id": portfolio_id,
        "seed": seed,
        "scenario": overrides.get("scenario", default_scenario),
        "solver_backend": overrides.get("solver_backend", "scipy"),
        "problem_type": overrides.get("problem_type", "lp"),
    }


def _domain_context(
    overrides: dict[str, Any],
    domain: str,
    workflow_id: str,
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
        "workflow_id": workflow_id,
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
