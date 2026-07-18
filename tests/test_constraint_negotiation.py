"""Tests for the constraint negotiation / inversion agent."""

from decision_intelligence.agents import negotiate_constraints
from decision_intelligence.contracts import Objective, ObjectiveDirection, OptimizationRequest
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import MoneyMarketOptimizer


def test_constraint_negotiation_ranks_sensitivity_proposals():
    registry = OptimizerRegistry()
    registry.register(MoneyMarketOptimizer())
    request = OptimizationRequest(
        domain="money_market",
        portfolio_id="PORT_NEGOTIATE",
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
            "solver_backend": "scipy",
            "problem_type": "lp",
        },
    )
    result = OptimizationOrchestrator(registry).run(request)

    negotiation = negotiate_constraints(result, target_improvement=5.0)

    assert negotiation.domain == "money_market"
    assert negotiation.proposals
    assert negotiation.proposals[0].source == "sensitivity"
    assert negotiation.proposals[0].governance_tier >= 2
    assert negotiation.recommendation.startswith("Start with")


def test_constraint_negotiation_uses_binding_constraints_without_sensitivities():
    negotiation = negotiate_constraints(
        {
            "domain": "money_market",
            "binding_constraints": ["prime_concentration", "single_fund_limit:FUND_1"],
            "sensitivities": [],
        }
    )

    assert [proposal.source for proposal in negotiation.proposals] == [
        "binding_constraint",
        "binding_constraint",
    ]
    assert negotiation.proposals[0].governance_tier == 5
