"""
Money Market Optimizer

Problem: allocate total cash across available MMFs to maximize net yield,
subject to:
  - Daily liquidity requirement (fraction of total cash redeemable T+0)
  - Weekly liquidity requirement
  - Minimum investment per fund (if allocated, must exceed threshold)
  - Client mandate: max fraction in prime funds
  - WAM constraint (portfolio WAM ≤ limit)

LP formulation (relaxed — minimum investment handled via threshold filtering):
  Variables: w[i] = fraction of total cash allocated to fund i
  Maximize:  Σ_i yield[i] × w[i]    (equivalently: minimize -Σ yield[i]×w[i])
  Subject to:
    (1) Σ_i w[i]  = 1                (fully invested)
    (2) Σ_i daily_liq[i] × w[i]  ≥  daily_liq_req
    (3) Σ_i weekly_liq[i] × w[i]  ≥  weekly_liq_req
    (4) Σ_i [i∈prime] × w[i]  ≤  max_prime_fraction
    (5) Σ_i WAM[i] × w[i]  ≤  max_wam
    (6) 0 ≤ w[i] ≤ max_single_fund (concentration)
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import linprog

from decision_intelligence.contracts import OptimizationRequest
from decision_intelligence.optimization.base import OptimizationCapability

from .data import CashPosition, MoneyMarketFund

_MAX_PRIME_FRACTION = 0.40   # ≤ 40% in prime funds
_MAX_WAM_DAYS = 60
_MAX_SINGLE_FUND = 0.50      # ≤ 50% in any single fund


class MoneyMarketOptimizer(OptimizationCapability):
    name = "Money Market Optimizer"
    version = "0.1.0"
    domain = "money_market"

    def validate_request(self, request: OptimizationRequest) -> list[str]:
        errors: list[str] = []
        if request.domain != self.domain:
            errors.append(f"Domain mismatch: expected '{self.domain}', got '{request.domain}'")
        if request.objective.metric not in ("yield", "net_yield", "expense_ratio"):
            errors.append(
                f"Unknown objective metric '{request.objective.metric}'. "
                "Supported: yield, net_yield, expense_ratio"
            )
        return errors

    def prepare_problem(self, request: OptimizationRequest) -> dict[str, Any]:
        from decision_intelligence.data import load_money_market

        funds, position = load_money_market(request)

        # Filter out funds below minimum investment
        min_alloc = request.context.get("min_investment_threshold", 250_000)
        eligible = [f for f in funds if f.min_investment <= min_alloc or
                    position.total_cash * 0.01 >= f.min_investment]
        n = len(eligible)

        yields = np.array([f.yield_7day for f in eligible])
        daily_liq = np.array([f.daily_liquidity_pct for f in eligible])
        weekly_liq = np.array([f.weekly_liquidity_pct for f in eligible])
        wam = np.array([f.wam_days for f in eligible])
        is_prime = np.array([1.0 if f.credit_quality == "prime" else 0.0 for f in eligible])

        # Objective: maximize yield → minimize negative yield
        c = -yields

        ctx = request.context
        max_prime = ctx.get("max_prime_fraction", _MAX_PRIME_FRACTION)
        max_wam = ctx.get("max_wam_days", _MAX_WAM_DAYS)
        max_single = ctx.get("max_single_fund", _MAX_SINGLE_FUND)
        daily_req = ctx.get("daily_liquidity_req", position.daily_liquidity_requirement)
        weekly_req = ctx.get("weekly_liquidity_req", position.weekly_liquidity_requirement)

        A_ub_rows, b_ub_rows = [], []

        # Daily liquidity: -Σ daily_liq[i]*w[i] ≤ -daily_req
        A_ub_rows.append(-daily_liq)
        b_ub_rows.append(-daily_req)

        # Weekly liquidity
        A_ub_rows.append(-weekly_liq)
        b_ub_rows.append(-weekly_req)

        # Prime concentration
        A_ub_rows.append(is_prime)
        b_ub_rows.append(max_prime)

        # WAM
        A_ub_rows.append(wam)
        b_ub_rows.append(max_wam)

        # Single-fund concentration: w[i] ≤ max_single (handled via bounds)
        A_ub = np.array(A_ub_rows)
        b_ub = np.array(b_ub_rows)

        # Equality: Σ w[i] = 1
        A_eq = np.ones((1, n))
        b_eq = np.array([1.0])

        bounds = [(0.0, max_single)] * n

        # Baseline: current allocation
        baseline_yield = _compute_current_yield(eligible, position)

        return {
            "funds": eligible,
            "position": position,
            "c": c,
            "A_ub": A_ub,
            "b_ub": b_ub,
            "A_eq": A_eq,
            "b_eq": b_eq,
            "bounds": bounds,
            "n": n,
            "yields": yields,
            "daily_liq": daily_liq,
            "weekly_liq": weekly_liq,
            "wam": wam,
            "is_prime": is_prime,
            "daily_req": daily_req,
            "weekly_req": weekly_req,
            "max_wam": max_wam,
            "max_prime": max_prime,
            "baseline_value": baseline_yield,
            "total_cash": position.total_cash,
        }

    def solve(self, problem: dict[str, Any]) -> dict[str, Any]:
        from decision_intelligence.contracts.results import SolveStatus

        res = linprog(
            c=problem["c"],
            A_ub=problem["A_ub"],
            b_ub=problem["b_ub"],
            A_eq=problem["A_eq"],
            b_eq=problem["b_eq"],
            bounds=problem["bounds"],
            method="highs",
        )

        if res.status == 0:
            w = res.x
            funds = problem["funds"]
            total_cash = problem["total_cash"]
            yields = problem["yields"]

            allocations = []
            for i, fund in enumerate(funds):
                if w[i] > 1e-6:
                    allocated = w[i] * total_cash
                    allocations.append({
                        "asset_id": fund.fund_id,
                        "label": fund.label,
                        "allocated_value": round(allocated, 2),
                        "allocated_fraction": round(w[i], 6),
                        "metadata": {
                            "yield_7day": fund.yield_7day,
                            "expense_ratio_bps": fund.expense_ratio_bps,
                            "wam_days": fund.wam_days,
                            "daily_liquidity_pct": fund.daily_liquidity_pct,
                            "credit_quality": fund.credit_quality,
                            "contribution_to_yield_bps": round(w[i] * fund.yield_7day * 100, 2),
                        },
                    })

            achieved_yield = float(-res.fun)
            binding = _find_binding(problem, w)

            return {
                "status": SolveStatus.OPTIMAL,
                "objective_value": achieved_yield,
                "w": w,
                "allocations": allocations,
                "binding_constraints": binding,
                "metadata": {"solver": "HiGHS", "n_funds_used": int((w > 1e-6).sum())},
            }
        else:
            from decision_intelligence.contracts.results import SolveStatus
            status_map = {2: SolveStatus.INFEASIBLE, 3: SolveStatus.UNBOUNDED}
            return {
                "status": status_map.get(res.status, SolveStatus.ERROR),
                "message": res.message,
            }

    def validate_solution(self, problem: dict[str, Any], solution: dict[str, Any]) -> list[str]:
        violations: list[str] = []
        w = solution.get("w")
        if w is None:
            return ["No solution vector"]

        tol = 1e-4
        if abs(w.sum() - 1.0) > tol:
            violations.append(f"Weights don't sum to 1: {w.sum():.6f}")

        dl = float(problem["daily_liq"] @ w)
        if dl < problem["daily_req"] - tol:
            violations.append(f"Daily liquidity {dl:.3f} < requirement {problem['daily_req']:.3f}")

        wl = float(problem["weekly_liq"] @ w)
        if wl < problem["weekly_req"] - tol:
            violations.append(f"Weekly liquidity {wl:.3f} < requirement {problem['weekly_req']:.3f}")

        return violations

    def run_sensitivity(self, problem: dict[str, Any], solution: dict[str, Any]) -> list[dict[str, Any]]:
        base_obj = solution["objective_value"]
        sensitivities = []

        # Sensitivity: relax daily liquidity requirement by 5pp
        for label, row_idx, direction, delta_pct, description in [
            ("daily_liquidity_req", 0, -1, 0.05, "daily liquidity requirement"),
            ("weekly_liquidity_req", 1, -1, 0.05, "weekly liquidity requirement"),
            ("max_prime_fraction", 2, +1, 0.10, "prime fund limit"),
        ]:
            b_mod = problem["b_ub"].copy()
            delta = delta_pct
            b_mod[row_idx] += direction * delta
            res = linprog(
                c=problem["c"],
                A_ub=problem["A_ub"],
                b_ub=b_mod,
                A_eq=problem["A_eq"],
                b_eq=problem["b_eq"],
                bounds=problem["bounds"],
                method="highs",
            )
            if res.status == 0:
                new_yield = -res.fun
                gain_bps = (new_yield - base_obj) * 100
                sensitivities.append({
                    "parameter": label,
                    "shadow_price": round(gain_bps / delta, 2),
                    "range_lower": round(problem["b_ub"][row_idx] * direction - 0.10, 4),
                    "range_upper": round(problem["b_ub"][row_idx] * direction + 0.10, 4),
                    "interpretation": (
                        f"Relaxing {description} by {delta_pct*100:.0f}pp "
                        f"improves yield by {gain_bps:.2f}bps"
                    ),
                })

        return sensitivities

    def explain(self, problem: dict[str, Any], solution: dict[str, Any]) -> str:
        funds = problem["funds"]
        w = solution["w"]
        opt_yield = solution["objective_value"]
        baseline = problem["baseline_value"]
        improvement_bps = (opt_yield - baseline) * 100

        dl = float(problem["daily_liq"] @ w)
        wl = float(problem["weekly_liq"] @ w)
        port_wam = float(problem["wam"] @ w)
        n_funds = int((w > 1e-6).sum())

        # Top allocations
        top = sorted(zip(w, funds), key=lambda t: -t[0])[:3]
        top_lines = "; ".join(f"{f.label} ({wi*100:.1f}%)" for wi, f in top if wi > 1e-6)

        binding = ", ".join(solution.get("binding_constraints", [])) or "none"

        return (
            f"Money market optimizer allocated ${problem['total_cash']/1e6:.0f}M across "
            f"{n_funds} funds.\n"
            f"Achieved net yield: {opt_yield:.4f}% vs baseline {baseline:.4f}% "
            f"— improvement of {improvement_bps:.2f}bps.\n"
            f"Portfolio liquidity: daily={dl:.1%}, weekly={wl:.1%}, WAM={port_wam:.0f}d.\n"
            f"Top allocations: {top_lines}.\n"
            f"Binding constraints: {binding}.\n"
            f"The optimizer concentrated in higher-yielding funds while respecting "
            f"daily/weekly liquidity floors and the WAM cap."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_current_yield(funds: list[MoneyMarketFund], position: CashPosition) -> float:
    total = position.total_cash
    if total == 0:
        return 0.0
    fund_map = {f.fund_id: f for f in funds}
    weighted = 0.0
    invested = 0.0
    for fid, amt in position.current_allocations.items():
        if fid in fund_map:
            weighted += fund_map[fid].yield_7day * amt
            invested += amt
    remaining = total - invested
    if remaining > 0 and funds:
        weighted += funds[0].yield_7day * remaining  # park in first fund
    return weighted / total if total else 0.0


def _find_binding(problem: dict[str, Any], w: np.ndarray) -> list[str]:
    tol = 0.005
    binding = []
    dl = float(problem["daily_liq"] @ w)
    if abs(dl - problem["daily_req"]) < tol:
        binding.append("daily_liquidity")
    wl = float(problem["weekly_liq"] @ w)
    if abs(wl - problem["weekly_req"]) < tol:
        binding.append("weekly_liquidity")
    pw = float(problem["is_prime"] @ w)
    if abs(pw - problem["max_prime"]) < tol:
        binding.append("prime_concentration")
    port_wam = float(problem["wam"] @ w)
    if abs(port_wam - problem["max_wam"]) < tol:
        binding.append("wam_limit")
    for i, fund in enumerate(problem["funds"]):
        if abs(w[i] - problem["bounds"][i][1]) < tol:
            binding.append(f"single_fund_limit:{fund.fund_id}")
    return binding
