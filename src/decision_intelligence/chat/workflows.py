"""Guided chat workflow specifications for supported optimizer domains."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from decision_intelligence.contracts import ObjectiveDirection

from .parser import (
    parse_amount,
    parse_float,
    parse_fraction,
    parse_int,
    parse_percent_points,
    parse_problem_type,
    parse_scenario_names,
    parse_solver_backend,
)

FieldTarget = Literal["portfolio", "context", "scenarios"]
Parser = Callable[[str], Any]


@dataclass(frozen=True)
class FieldSpec:
    key: str
    prompt: str
    parser: Parser
    default: Any
    target: FieldTarget = "context"
    label: str | None = None

    @property
    def display_label(self) -> str:
        return self.label or self.key.replace("_", " ")


@dataclass(frozen=True)
class WorkflowSpec:
    domain: str
    title: str
    intro: str
    objective_metric: str
    direction: ObjectiveDirection
    fields: tuple[FieldSpec, ...]
    base_context: dict[str, Any]


SCENARIO_PRESETS: dict[str, dict[str, dict[str, Any]]] = {
    "stress": {
        "collateral": {"obligation_scale": 1.5},
        "money_market": {"daily_liquidity_req": 0.40, "weekly_liquidity_req": 0.70},
        "financing": {"spread_shift": 1.5, "capacity_scale": 0.6},
        "asset_allocation": {
            "equity_return_shift": -0.025,
            "volatility_scale": 1.35,
            "min_cash_weight": 0.05,
        },
    },
    "credit_stress": {
        "collateral": {"obligation_scale": 1.3},
        "money_market": {"daily_liquidity_req": 0.45, "yield_shift": 0.92},
        "financing": {"spread_shift": 1.5, "capacity_scale": 0.6},
        "asset_allocation": {
            "equity_return_shift": -0.035,
            "bond_return_shift": -0.005,
            "volatility_scale": 1.50,
            "min_cash_weight": 0.06,
        },
    },
    "downside": {
        "collateral": {"inventory_scale": 0.7},
        "money_market": {"yield_shift": 0.9},
        "financing": {"spread_shift": 1.2, "capacity_scale": 0.8},
        "asset_allocation": {"return_shift": -0.01, "volatility_scale": 1.20},
    },
    "inventory": {
        "collateral": {"inventory_scale": 0.7},
        "money_market": {},
        "financing": {},
        "asset_allocation": {},
    },
}


def _identity(text: str) -> str:
    value = text.strip()
    if not value:
        raise ValueError("Enter a value.")
    return value


def _parse_optional_fraction(text: str) -> float | None:
    if text.strip().lower() in {"none", "no"}:
        return None
    return parse_fraction(text)


SOLVER_FIELDS = (
    FieldSpec(
        "solver_backend",
        "Which optimization engine should I use? Type scipy or cvxpy.",
        parse_solver_backend,
        "scipy",
        label="solver backend",
    ),
    FieldSpec(
        "problem_type",
        "What problem type should I solve? Type lp, milp, qp, or conic.",
        parse_problem_type,
        "lp",
        label="problem type",
    ),
)


WORKFLOWS: dict[str, WorkflowSpec] = {
    "asset_allocation": WorkflowSpec(
        domain="asset_allocation",
        title="Asset Allocation MVO",
        intro="I will guide a multi-asset mean-variance allocation workflow.",
        objective_metric="utility",
        direction=ObjectiveDirection.MAXIMIZE,
        base_context={},
        fields=(
            FieldSpec(
                "portfolio_id",
                "What portfolio ID should I use?",
                _identity,
                "PORT_001",
                "portfolio",
                "portfolio",
            ),
            FieldSpec(
                "portfolio_notional",
                "What portfolio notional should I allocate?",
                parse_amount,
                100_000_000,
                label="portfolio notional",
            ),
            FieldSpec(
                "target_return",
                "Target annual return? Type none, or a value like 5%.",
                _parse_optional_fraction,
                None,
                label="target return",
            ),
            FieldSpec(
                "risk_aversion",
                "Risk aversion lambda? Use 3 for balanced, lower for aggressive.",
                parse_float,
                3.0,
                label="risk aversion",
            ),
            FieldSpec(
                "max_single_asset_weight",
                "Maximum single asset-class weight? (for example 45%)",
                parse_fraction,
                0.45,
                label="single asset cap",
            ),
            FieldSpec(
                "min_cash_weight",
                "Minimum cash allocation? (for example 2%)",
                parse_fraction,
                0.02,
                label="cash floor",
            ),
            *SOLVER_FIELDS,
            FieldSpec(
                "scenario_names",
                "Scenario to include? Type none, stress, credit stress, or downside.",
                parse_scenario_names,
                [],
                "scenarios",
                "scenarios",
            ),
        ),
    ),
    "money_market": WorkflowSpec(
        domain="money_market",
        title="Money Market Optimization",
        intro="I will guide a money market allocation workflow.",
        objective_metric="yield",
        direction=ObjectiveDirection.MAXIMIZE,
        base_context={"n_funds": 8},
        fields=(
            FieldSpec(
                "portfolio_id",
                "What portfolio ID should I use?",
                _identity,
                "PORT_001",
                "portfolio",
                "portfolio",
            ),
            FieldSpec("total_cash", "How much cash are you allocating?", parse_amount, 500_000_000),
            FieldSpec(
                "daily_liquidity_req",
                "Minimum daily liquidity? (for example 30%)",
                parse_fraction,
                0.30,
                label="daily liquidity",
            ),
            FieldSpec(
                "weekly_liquidity_req",
                "Minimum weekly liquidity? (for example 60%)",
                parse_fraction,
                0.60,
                label="weekly liquidity",
            ),
            FieldSpec(
                "max_prime_fraction",
                "Maximum prime fund concentration? (for example 40%)",
                parse_fraction,
                0.40,
                label="prime fund limit",
            ),
            FieldSpec("max_wam_days", "Maximum WAM in days?", parse_int, 60, label="max WAM"),
            FieldSpec(
                "max_single_fund",
                "Maximum single-fund concentration? (for example 50%)",
                parse_fraction,
                0.50,
                label="single-fund limit",
            ),
            FieldSpec(
                "max_funds",
                "Maximum number of funds if using MILP fund selection?",
                parse_int,
                4,
                label="max selected funds",
            ),
            FieldSpec(
                "min_allocation_fraction",
                "Minimum allocation per selected fund if using MILP? (for example 5%)",
                parse_fraction,
                0.05,
                label="minimum selected allocation",
            ),
            *SOLVER_FIELDS,
            FieldSpec(
                "scenario_names",
                "Scenario to include? Type none, stress, credit stress, downside, or inventory.",
                parse_scenario_names,
                [],
                "scenarios",
                "scenarios",
            ),
        ),
    ),
    "financing": WorkflowSpec(
        domain="financing",
        title="Financing Optimization",
        intro="I will guide a financing-source optimization workflow.",
        objective_metric="funding_spread",
        direction=ObjectiveDirection.MINIMIZE,
        base_context={"n_counterparties": 10},
        fields=(
            FieldSpec(
                "portfolio_id",
                "What portfolio ID should I use?",
                _identity,
                "PORT_001",
                "portfolio",
                "portfolio",
            ),
            FieldSpec(
                "total_funding_need",
                "How much funding do you need?",
                parse_amount,
                300_000_000,
                label="funding need",
            ),
            FieldSpec(
                "max_cp_concentration",
                "Maximum counterparty concentration? (for example 40%)",
                parse_fraction,
                0.40,
                label="counterparty limit",
            ),
            FieldSpec(
                "capital_budget_pct",
                "Capital budget as percent of funding? (for example 5%)",
                parse_percent_points,
                5.0,
                label="capital budget",
            ),
            *SOLVER_FIELDS,
            FieldSpec(
                "scenario_names",
                "Scenario to include? Type none, stress, credit stress, downside, or inventory.",
                parse_scenario_names,
                [],
                "scenarios",
                "scenarios",
            ),
        ),
    ),
    "collateral": WorkflowSpec(
        domain="collateral",
        title="Collateral Optimization",
        intro="I will guide a collateral-allocation optimization workflow.",
        objective_metric="funding_cost",
        direction=ObjectiveDirection.MINIMIZE,
        base_context={"n_assets": 20},
        fields=(
            FieldSpec(
                "portfolio_id",
                "What portfolio ID should I use?",
                _identity,
                "PORT_001",
                "portfolio",
                "portfolio",
            ),
            FieldSpec(
                "n_assets",
                "How many simulated collateral assets should I model?",
                parse_int,
                20,
            ),
            FieldSpec(
                "concentration_limit",
                "Maximum single asset-class concentration per obligation? (for example 60%)",
                parse_fraction,
                0.60,
                label="asset-class concentration",
            ),
            *SOLVER_FIELDS,
            FieldSpec(
                "scenario_names",
                "Scenario to include? Type none, stress, credit stress, downside, or inventory.",
                parse_scenario_names,
                [],
                "scenarios",
                "scenarios",
            ),
        ),
    ),
}
