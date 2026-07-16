"""Guided chat workflow specifications for supported optimizer domains."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from decision_intelligence.contracts import ObjectiveDirection

from .parser import (
    parse_amount,
    parse_fraction,
    parse_int,
    parse_percent_points,
    parse_scenario_names,
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
    },
    "credit_stress": {
        "collateral": {"obligation_scale": 1.3},
        "money_market": {"daily_liquidity_req": 0.45, "yield_shift": 0.92},
        "financing": {"spread_shift": 1.5, "capacity_scale": 0.6},
    },
    "downside": {
        "collateral": {"inventory_scale": 0.7},
        "money_market": {"yield_shift": 0.9},
        "financing": {"spread_shift": 1.2, "capacity_scale": 0.8},
    },
    "inventory": {
        "collateral": {"inventory_scale": 0.7},
        "money_market": {},
        "financing": {},
    },
}


def _identity(text: str) -> str:
    value = text.strip()
    if not value:
        raise ValueError("Enter a value.")
    return value


WORKFLOWS: dict[str, WorkflowSpec] = {
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
            FieldSpec("n_assets", "How many simulated collateral assets should I model?", parse_int, 20),
            FieldSpec(
                "concentration_limit",
                "Maximum single asset-class concentration per obligation? (for example 60%)",
                parse_fraction,
                0.60,
                label="asset-class concentration",
            ),
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
