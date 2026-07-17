"""
Asset Allocation MVO Optimizer

Problem: allocate capital across major asset classes with a simple
mean-variance objective.

Variables:
  w[i] = portfolio weight in asset class i

Default objective:
  maximize expected_return(w) - risk_aversion * variance(w)

Constraints:
  - fully invested: sum(w) = 1
  - long-only lower/upper bounds per asset class
  - optional target_return floor
  - optional aggregate minimum/maximum class exposures
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import minimize

from decision_intelligence.contracts import OptimizationRequest
from decision_intelligence.contracts.results import SolveStatus
from decision_intelligence.optimization.base import OptimizationCapability

from .data import AssetClassAssumption

_DEFAULT_RISK_AVERSION = 3.0
_DEFAULT_PORTFOLIO_NOTIONAL = 100_000_000.0


class AssetAllocationMVOOptimizer(OptimizationCapability):
    name = "Asset Allocation MVO Optimizer"
    version = "0.1.0"
    domain = "asset_allocation"

    def validate_request(self, request: OptimizationRequest) -> list[str]:
        errors: list[str] = []
        if request.domain != self.domain:
            errors.append(f"Domain mismatch: expected '{self.domain}', got '{request.domain}'")
        if request.objective.metric not in {
            "utility",
            "risk_adjusted_return",
            "sharpe",
            "volatility",
        }:
            errors.append(
                f"Unknown objective metric '{request.objective.metric}'. "
                "Supported: utility, risk_adjusted_return, sharpe, volatility"
            )
        risk_aversion = float(request.context.get("risk_aversion", _DEFAULT_RISK_AVERSION))
        if risk_aversion < 0:
            errors.append("risk_aversion must be non-negative.")
        target_return = request.context.get("target_return")
        if target_return is not None and not 0 <= float(target_return) <= 0.30:
            errors.append("target_return must be an annual decimal between 0 and 0.30.")
        return errors

    def prepare_problem(self, request: OptimizationRequest) -> dict[str, Any]:
        from decision_intelligence.data import load_asset_allocation

        assets, covariance = load_asset_allocation(request)
        expected_returns = np.array([asset.expected_return for asset in assets])
        current = np.array([asset.current_weight for asset in assets], dtype=float)
        current = current / current.sum()
        bounds = [(asset.min_weight, asset.max_weight) for asset in assets]
        risk_aversion = float(request.context.get("risk_aversion", _DEFAULT_RISK_AVERSION))
        target_return = request.context.get("target_return")

        baseline_value = _portfolio_utility(
            current,
            expected_returns,
            covariance,
            risk_aversion,
            request.objective.metric,
        )

        return {
            "assets": assets,
            "expected_returns": expected_returns,
            "covariance": covariance,
            "current_weights": current,
            "bounds": bounds,
            "risk_aversion": risk_aversion,
            "target_return": None if target_return is None else float(target_return),
            "portfolio_notional": float(
                request.context.get("portfolio_notional", _DEFAULT_PORTFOLIO_NOTIONAL)
            ),
            "min_class_weights": request.context.get("min_class_weights", {}),
            "max_class_weights": request.context.get("max_class_weights", {}),
            "metric": request.objective.metric,
            "baseline_value": baseline_value,
            "solver_backend": request.context.get("solver_backend", "scipy"),
            "problem_type": request.context.get("problem_type", "qp"),
        }

    def solve(self, problem: dict[str, Any]) -> dict[str, Any]:
        assets = problem["assets"]
        expected_returns = problem["expected_returns"]
        covariance = problem["covariance"]
        risk_aversion = problem["risk_aversion"]
        metric = problem["metric"]

        constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
        if problem["target_return"] is not None:
            target = problem["target_return"]
            constraints.append(
                {
                    "type": "ineq",
                    "fun": lambda w, target=target: float(
                        w @ expected_returns - target
                    ),
                }
            )

        constraints.extend(_class_weight_constraints(assets, problem))

        result = minimize(
            lambda w: -_portfolio_utility(w, expected_returns, covariance, risk_aversion, metric),
            problem["current_weights"],
            method="SLSQP",
            bounds=problem["bounds"],
            constraints=constraints,
            options={"ftol": 1e-10, "maxiter": 500},
        )

        if not result.success:
            return {"status": SolveStatus.INFEASIBLE, "message": result.message}

        weights = np.clip(result.x, 0.0, 1.0)
        weights = weights / weights.sum()
        expected_return, volatility, variance, sharpe = _portfolio_stats(
            weights,
            expected_returns,
            covariance,
        )
        objective_value = _portfolio_utility(
            weights,
            expected_returns,
            covariance,
            risk_aversion,
            metric,
        )

        return {
            "status": SolveStatus.OPTIMAL,
            "objective_value": objective_value,
            "weights": weights,
            "expected_return": expected_return,
            "volatility": volatility,
            "variance": variance,
            "sharpe": sharpe,
            "allocations": _build_allocations(problem, weights),
            "binding_constraints": _find_binding(problem, weights),
            "metadata": {
                "solver_backend": "scipy",
                "problem_type": "qp",
                "solver_method": "SLSQP",
                "risk_aversion": risk_aversion,
                "expected_return": expected_return,
                "volatility": volatility,
                "variance": variance,
                "sharpe": sharpe,
                "target_return": problem["target_return"],
                "asset_count": len(assets),
            },
        }

    def validate_solution(
        self,
        problem: dict[str, Any],
        solution: dict[str, Any],
    ) -> list[str]:
        weights = solution.get("weights")
        if weights is None:
            return ["No solution weights returned."]

        violations: list[str] = []
        tol = 1e-5
        if abs(float(np.sum(weights)) - 1.0) > tol:
            violations.append(f"Weights do not sum to 1.0: {np.sum(weights):.6f}")

        for weight, asset, (lower, upper) in zip(weights, problem["assets"], problem["bounds"]):
            if weight < lower - tol:
                violations.append(f"{asset.label} weight {weight:.2%} is below {lower:.2%}.")
            if weight > upper + tol:
                violations.append(f"{asset.label} weight {weight:.2%} exceeds {upper:.2%}.")

        target = problem["target_return"]
        if target is not None and solution["expected_return"] < target - tol:
            violations.append(
                f"Expected return {solution['expected_return']:.2%} is below "
                f"target {target:.2%}."
            )
        return violations

    def run_sensitivity(
        self,
        problem: dict[str, Any],
        solution: dict[str, Any],
    ) -> list[dict[str, Any]]:
        base_utility = solution["objective_value"]
        sensitivities: list[dict[str, Any]] = []

        for label, risk_aversion in [
            ("risk_aversion_down_25pct", problem["risk_aversion"] * 0.75),
            ("risk_aversion_up_25pct", problem["risk_aversion"] * 1.25),
        ]:
            alt = dict(problem)
            alt["risk_aversion"] = risk_aversion
            solved = self.solve(alt)
            if solved["status"] == SolveStatus.OPTIMAL:
                sensitivities.append(
                    {
                        "parameter": label,
                        "shadow_price": round(solved["objective_value"] - base_utility, 6),
                        "range_lower": round(risk_aversion, 4),
                        "range_upper": round(risk_aversion, 4),
                        "interpretation": (
                            f"Changing risk aversion to {risk_aversion:.2f} moves "
                            f"utility by {solved['objective_value'] - base_utility:.4f}."
                        ),
                    }
                )

        return sensitivities

    def explain(self, problem: dict[str, Any], solution: dict[str, Any]) -> str:
        weights = solution["weights"]
        assets = problem["assets"]
        top = sorted(zip(weights, assets), key=lambda item: -item[0])[:3]
        top_text = "; ".join(
            f"{asset.label} {weight:.1%}" for weight, asset in top if weight > 1e-5
        )
        binding = ", ".join(solution.get("binding_constraints", [])) or "none"
        return (
            "Asset allocation MVO selected a long-only multi-asset portfolio "
            f"with expected return {solution['expected_return']:.2%}, volatility "
            f"{solution['volatility']:.2%}, and Sharpe {solution['sharpe']:.2f}. "
            f"Top allocations: {top_text}. Binding constraints: {binding}. "
            "The objective balances expected return against variance using the "
            f"risk-aversion setting {problem['risk_aversion']:.2f}."
        )


def _portfolio_stats(
    weights: np.ndarray,
    expected_returns: np.ndarray,
    covariance: np.ndarray,
) -> tuple[float, float, float, float]:
    expected_return = float(weights @ expected_returns)
    variance = float(weights @ covariance @ weights)
    volatility = float(np.sqrt(max(variance, 0.0)))
    sharpe = expected_return / volatility if volatility > 0 else 0.0
    return expected_return, volatility, variance, sharpe


def _portfolio_utility(
    weights: np.ndarray,
    expected_returns: np.ndarray,
    covariance: np.ndarray,
    risk_aversion: float,
    metric: str,
) -> float:
    expected_return, volatility, variance, sharpe = _portfolio_stats(
        weights,
        expected_returns,
        covariance,
    )
    if metric == "volatility":
        return -volatility
    if metric == "sharpe":
        return sharpe
    return expected_return - risk_aversion * variance


def _class_weight_constraints(
    assets: list[AssetClassAssumption],
    problem: dict[str, Any],
) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    for asset_class, minimum in problem["min_class_weights"].items():
        indexes = [idx for idx, asset in enumerate(assets) if asset.asset_class == asset_class]
        constraints.append(
            {
                "type": "ineq",
                "fun": lambda w, indexes=indexes, minimum=float(minimum): (
                    float(np.sum(w[indexes]) - minimum)
                ),
            }
        )
    for asset_class, maximum in problem["max_class_weights"].items():
        indexes = [idx for idx, asset in enumerate(assets) if asset.asset_class == asset_class]
        constraints.append(
            {
                "type": "ineq",
                "fun": lambda w, indexes=indexes, maximum=float(maximum): (
                    float(maximum - np.sum(w[indexes]))
                ),
            }
        )
    return constraints


def _build_allocations(problem: dict[str, Any], weights: np.ndarray) -> list[dict[str, Any]]:
    expected_returns = problem["expected_returns"]
    covariance = problem["covariance"]
    portfolio_notional = problem["portfolio_notional"]
    portfolio_variance = float(weights @ covariance @ weights)
    allocations = []
    for index, (asset, weight) in enumerate(zip(problem["assets"], weights)):
        variance_contribution = (
            weight * float((covariance @ weights)[index]) / portfolio_variance
            if portfolio_variance > 0
            else 0.0
        )
        allocations.append(
            {
                "asset_id": asset.asset_id,
                "label": asset.label,
                "allocated_value": round(float(weight * portfolio_notional), 2),
                "allocated_fraction": round(float(weight), 6),
                "metadata": {
                    "asset_class": asset.asset_class,
                    "expected_return": asset.expected_return,
                    "volatility": asset.volatility,
                    "current_weight": asset.current_weight,
                    "min_weight": asset.min_weight,
                    "max_weight": asset.max_weight,
                    "return_contribution": round(float(weight * expected_returns[index]), 6),
                    "risk_contribution": round(float(variance_contribution), 6),
                    **asset.metadata,
                },
            }
        )
    return allocations


def _find_binding(problem: dict[str, Any], weights: np.ndarray) -> list[str]:
    binding: list[str] = []
    tol = 1e-4
    for asset, weight, (lower, upper) in zip(
        problem["assets"],
        weights,
        problem["bounds"],
    ):
        if abs(weight - lower) < tol:
            binding.append(f"min_weight:{asset.asset_id}")
        if abs(weight - upper) < tol:
            binding.append(f"max_weight:{asset.asset_id}")

    target = problem["target_return"]
    if target is not None:
        expected_return = float(weights @ problem["expected_returns"])
        if abs(expected_return - target) < tol:
            binding.append("target_return")
    return binding
