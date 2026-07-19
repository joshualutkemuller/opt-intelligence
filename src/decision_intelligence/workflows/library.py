"""Reusable workflow builders for higher-level optimization demos."""

from __future__ import annotations

from typing import Any

from decision_intelligence.contracts import Objective, ObjectiveDirection, OptimizationRequest
from decision_intelligence.contracts.requests import ExecutionMode

from .types import WorkflowDependencyRule, WorkflowPlan, WorkflowStep

LIQUIDITY_STRESS_WORKFLOW_ID = "liquidity_stress_funding_workflow"
FUNDING_CAPACITY_SHOCK_WORKFLOW_ID = "funding_capacity_shock"
COLLATERAL_LIQUIDITY_REVIEW_WORKFLOW_ID = "collateral_liquidity_review"
PORTFOLIO_REBALANCE_MVO_WORKFLOW_ID = "portfolio_rebalance_mvo"
MONEY_MARKET_POLICY_OPTIMIZATION_WORKFLOW_ID = "money_market_policy_optimization"
TREASURY_CASH_MOVEMENT_WORKFLOW_ID = "treasury_cash_movement"
MARGIN_CALL_WORKFLOW_ID = "margin_call_workflow"

_PRODUCTION_ADAPTER_BY_DOMAIN = {
    "asset_allocation": "production.asset_allocation.mvo",
    "collateral": "production.collateral.allocation",
    "margin_operations": "production.margin_call.workflow",
    "money_market": "production.money_market.allocation",
    "treasury_operations": "production.treasury.cash_movement",
}

_DOMAIN_BY_PRODUCTION_ADAPTER = {
    adapter_id: domain for domain, adapter_id in _PRODUCTION_ADAPTER_BY_DOMAIN.items()
}


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


def build_portfolio_rebalance_mvo_workflow(
    *,
    portfolio_id: str = "PORT_001",
    seed: int = 42,
    context: dict[str, Any] | None = None,
) -> WorkflowPlan:
    """Build a one-step multi-asset MVO rebalance workflow."""

    overrides = dict(context or {})
    workflow_context = _workflow_context(portfolio_id, seed, overrides, "mvo_rebalance")
    workflow_context["problem_type"] = overrides.get("problem_type", "qp")
    asset_context = _domain_context(
        overrides,
        "asset_allocation",
        PORTFOLIO_REBALANCE_MVO_WORKFLOW_ID,
        {
            "portfolio_notional": 250_000_000,
            "target_return": 0.05,
            "risk_aversion": 3.0,
            "max_single_asset_weight": 0.45,
            "min_cash_weight": 0.02,
            "solver_backend": "scipy",
            "problem_type": "qp",
        },
        workflow_context,
    )

    return WorkflowPlan(
        workflow_id=PORTFOLIO_REBALANCE_MVO_WORKFLOW_ID,
        name="Portfolio Rebalance MVO",
        description=(
            "Runs a constrained mean-variance optimizer for a multi-asset "
            "portfolio rebalance."
        ),
        context=workflow_context,
        steps=[
            WorkflowStep(
                step_id="asset_allocation_001",
                domain="asset_allocation",
                name="Multi-asset MVO rebalance",
                description=(
                    "Allocate capital across asset classes using expected return, "
                    "covariance, target return, and concentration limits."
                ),
                request=_request(
                    domain="asset_allocation",
                    portfolio_id=portfolio_id,
                    direction=ObjectiveDirection.MAXIMIZE,
                    metric="utility",
                    context=asset_context,
                ),
            ),
        ],
    )


def build_money_market_policy_optimization_workflow(
    *,
    portfolio_id: str = "PORT_001",
    seed: int = 42,
    context: dict[str, Any] | None = None,
) -> WorkflowPlan:
    """Build a one-step money-market allocation workflow from a policy document."""

    overrides = dict(context or {})
    workflow_context = _workflow_context(portfolio_id, seed, overrides, "money_market_policy")
    workflow_context["problem_type"] = overrides.get("problem_type", "lp")
    money_market_context = _domain_context(
        overrides,
        "money_market",
        MONEY_MARKET_POLICY_OPTIMIZATION_WORKFLOW_ID,
        {
            "n_funds": 8,
            "total_cash": 500_000_000,
            "daily_liquidity_req": 0.30,
            "weekly_liquidity_req": 0.60,
            "max_prime_fraction": 0.40,
            "max_wam_days": 55,
            "max_single_fund": 0.45,
            "max_funds": 4,
            "min_allocation_fraction": 0.05,
        },
        workflow_context,
    )

    return WorkflowPlan(
        workflow_id=MONEY_MARKET_POLICY_OPTIMIZATION_WORKFLOW_ID,
        name="Money Market Policy Optimization",
        description=(
            "Runs a one-step money-market allocation optimizer from a parsed "
            "cash policy, mandate, or portfolio review document."
        ),
        context=workflow_context,
        steps=[
            WorkflowStep(
                step_id="money_market_001",
                domain="money_market",
                name="Policy-constrained liquidity allocation",
                description=(
                    "Allocate cash across eligible money-market funds while "
                    "respecting liquidity floors, prime exposure, WAM, and "
                    "single-fund limits from the ingested document."
                ),
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


def build_treasury_cash_movement_workflow(
    *,
    portfolio_id: str = "PORT_001",
    seed: int = 42,
    context: dict[str, Any] | None = None,
) -> WorkflowPlan:
    """Build a one-step production treasury cash movement workflow."""

    overrides = dict(context or {})
    workflow_context = _workflow_context(portfolio_id, seed, overrides, "treasury_cash_movement")
    workflow_context["optimizer_runtime"] = "production"
    workflow_context["production_optimizer_id"] = "production.treasury.cash_movement"
    treasury_context = _domain_context(
        overrides,
        "treasury_operations",
        TREASURY_CASH_MOVEMENT_WORKFLOW_ID,
        {
            "optimizer_runtime": "production",
            "production_optimizer_id": "production.treasury.cash_movement",
            "cutoff_hour": 15,
            "stress_multiplier": 1.0,
            "cash_balances": [
                {
                    "account_id": "SRC_1",
                    "entity": "Broker Dealer",
                    "currency": "USD",
                    "available_cash": 150_000_000,
                    "minimum_buffer": 20_000_000,
                },
                {
                    "account_id": "SRC_2",
                    "entity": "Bank Entity",
                    "currency": "USD",
                    "available_cash": 80_000_000,
                    "minimum_buffer": 15_000_000,
                },
            ],
            "funding_requirements": [
                {
                    "requirement_id": "PAY_A",
                    "target_account_id": "CLEARING_A",
                    "currency": "USD",
                    "required_cash": 90_000_000,
                    "cutoff_hour": 15,
                },
                {
                    "requirement_id": "PAY_B",
                    "target_account_id": "SETTLEMENT_B",
                    "currency": "USD",
                    "required_cash": 65_000_000,
                    "cutoff_hour": 16,
                },
            ],
            "payment_rails": [
                {
                    "rail_id": "FEDWIRE",
                    "currency": "USD",
                    "fee_bps": 0.15,
                    "fixed_fee": 35,
                    "cutoff_hour": 17,
                    "max_transfer": 250_000_000,
                },
                {
                    "rail_id": "CHIPS",
                    "currency": "USD",
                    "fee_bps": 0.08,
                    "fixed_fee": 20,
                    "cutoff_hour": 16,
                    "max_transfer": 125_000_000,
                },
            ],
        },
        workflow_context,
    )

    return WorkflowPlan(
        workflow_id=TREASURY_CASH_MOVEMENT_WORKFLOW_ID,
        name="Treasury Cash Movement",
        description=(
            "Routes operational cash to clearing and settlement requirements "
            "through open payment rails while preserving source buffers."
        ),
        context=workflow_context,
        steps=[
            WorkflowStep(
                step_id="treasury_cash_001",
                domain="treasury_operations",
                name="Treasury cash movement routing",
                description=(
                    "Minimize payment cost and cutoff risk while satisfying "
                    "same-day funding requirements."
                ),
                request=_request(
                    domain="treasury_operations",
                    portfolio_id=portfolio_id,
                    direction=ObjectiveDirection.MINIMIZE,
                    metric="transfer_cost",
                    context=treasury_context,
                ),
            ),
        ],
    )


def build_margin_call_workflow(
    *,
    portfolio_id: str = "PORT_001",
    seed: int = 42,
    context: dict[str, Any] | None = None,
) -> WorkflowPlan:
    """Build a one-step production margin-call workflow prioritization run."""

    overrides = dict(context or {})
    workflow_context = _workflow_context(portfolio_id, seed, overrides, "margin_call_workflow")
    workflow_context["optimizer_runtime"] = "production"
    workflow_context["production_optimizer_id"] = "production.margin_call.workflow"
    margin_context = _domain_context(
        overrides,
        "margin_operations",
        MARGIN_CALL_WORKFLOW_ID,
        {
            "optimizer_runtime": "production",
            "production_optimizer_id": "production.margin_call.workflow",
            "team_capacity_minutes": 150,
            "materiality_threshold": 25_000_000,
            "dispute_stress_multiplier": 1.0,
            "margin_call_queue": [
                {
                    "call_id": "MC_A",
                    "counterparty": "Dealer A",
                    "amount": 40_000_000,
                    "due_in_hours": 2,
                    "dispute_probability": 0.20,
                    "ops_minutes": 80,
                    "risk_tier": "high",
                },
                {
                    "call_id": "MC_B",
                    "counterparty": "CCP B",
                    "amount": 70_000_000,
                    "due_in_hours": 1,
                    "dispute_probability": 0.05,
                    "ops_minutes": 70,
                    "risk_tier": "critical",
                },
                {
                    "call_id": "MC_C",
                    "counterparty": "Dealer C",
                    "amount": 15_000_000,
                    "due_in_hours": 8,
                    "dispute_probability": 0.60,
                    "ops_minutes": 90,
                    "risk_tier": "medium",
                },
            ],
        },
        workflow_context,
    )

    return WorkflowPlan(
        workflow_id=MARGIN_CALL_WORKFLOW_ID,
        name="Margin Call Workflow",
        description=(
            "Prioritizes margin calls by exposure, SLA urgency, dispute risk, "
            "counterparty tier, and available operations capacity."
        ),
        context=workflow_context,
        steps=[
            WorkflowStep(
                step_id="margin_call_001",
                domain="margin_operations",
                name="Margin call queue prioritization",
                description=(
                    "Assign the highest-risk margin calls inside the current "
                    "team capacity window and explain deferrals."
                ),
                request=_request(
                    domain="margin_operations",
                    portfolio_id=portfolio_id,
                    direction=ObjectiveDirection.MINIMIZE,
                    metric="residual_risk",
                    context=margin_context,
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
            "asset_allocation",
            "treasury_operations",
            "margin_operations",
            "scenario",
        }
    }
    domain_overrides = overrides.get(domain, {})
    if domain_overrides is None:
        domain_overrides = {}
    if not isinstance(domain_overrides, dict):
        raise TypeError(f"context['{domain}'] must be a dict when provided.")

    context = {
        **workflow_context,
        **defaults,
        **shared,
        **domain_overrides,
        "workflow_id": workflow_id,
        "workflow_domain": domain,
    }
    return _runtime_context_for_domain(context, domain)


def _runtime_context_for_domain(
    context: dict[str, Any],
    domain: str,
) -> dict[str, Any]:
    """Apply production runtime only to workflow domains with adapters."""

    if context.get("optimizer_runtime") != "production":
        context.pop("production_optimizer_id", None)
        return {**context, "optimizer_runtime": "phase1"}

    configured_adapter = context.get("production_optimizer_id")
    configured_domain = (
        _DOMAIN_BY_PRODUCTION_ADAPTER.get(str(configured_adapter))
        if configured_adapter
        else None
    )
    default_adapter = _PRODUCTION_ADAPTER_BY_DOMAIN.get(domain)

    if configured_domain and configured_domain != domain:
        context.pop("production_optimizer_id", None)
        return {**context, "optimizer_runtime": "phase1"}

    adapter_id = str(configured_adapter or default_adapter or "")
    if not adapter_id:
        context.pop("production_optimizer_id", None)
        return {**context, "optimizer_runtime": "phase1"}

    return {
        **context,
        "optimizer_runtime": "production",
        "production_optimizer_id": adapter_id,
    }


def _request(
    *,
    domain: str,
    portfolio_id: str,
    direction: ObjectiveDirection,
    metric: str,
    context: dict[str, Any],
) -> OptimizationRequest:
    execution_mode = ExecutionMode(context.get("execution_mode", ExecutionMode.RECOMMENDATION))
    return OptimizationRequest(
        domain=domain,
        portfolio_id=portfolio_id,
        objective=Objective(
            name=f"{direction.value}_{metric}",
            direction=direction,
            metric=metric,
        ),
        execution_mode=execution_mode,
        context=context,
        requestor="workflow",
    )
