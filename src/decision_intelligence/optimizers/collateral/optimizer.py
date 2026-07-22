"""
Collateral Optimizer

Problem: allocate collateral assets to satisfy counterparty obligations at
minimum total funding cost (funding_cost_bps × allocated market value), subject to:
  - Eligibility per counterparty
  - Haircut-adjusted value covers obligation
  - No asset allocated beyond its inventory
  - Maximum concentration per asset class (configurable)

LP formulation:
  Variables: x[i, j] = fraction of asset i allocated to obligation j
  Minimize:  Σ_i Σ_j  funding_cost_bps[i] × market_value[i] × x[i,j]  / 10000
  Subject to:
    (1) Σ_j x[i,j]  ≤ 1                            (inventory)
    (2) Σ_i x[i,j] × (1 - haircut[i]) × mv[i] ≥ required_value[j]   (coverage)
    (3) x[i,j] = 0  if asset i not eligible for obligation j           (eligibility)
    (4) Σ_i x[i,j] × mv[i] / Σ_k x[k,j] × mv[k]  ≤ conc_limit[class]  (concentration, linearized)
    (5) 0 ≤ x[i,j] ≤ 1
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import linprog

from decision_intelligence.contracts import OptimizationRequest
from decision_intelligence.optimization.base import OptimizationCapability
from decision_intelligence.solvers import (
    LinearProblem,
    SolverConfigError,
    SolverSpec,
    solve_linear_problem,
)

from .data import CollateralAsset, CollateralObligation

_CONCENTRATION_LIMIT = 0.60   # max 60% from any single asset class per obligation

# Assets with funding_cost_bps above this threshold are considered high-demand
# securities-lending candidates.  Posting them as collateral forgoes that rebate.
_LENDING_OPPORTUNITY_THRESHOLD_BPS = 30.0


class CollateralOptimizer(OptimizationCapability):
    name = "Collateral Optimizer"
    version = "0.1.0"
    domain = "collateral"

    def validate_request(self, request: OptimizationRequest) -> list[str]:
        errors: list[str] = []
        if request.domain != self.domain:
            errors.append(f"Domain mismatch: expected '{self.domain}', got '{request.domain}'")
        if request.objective.metric not in ("funding_cost", "haircut_cost", "opportunity_cost"):
            errors.append(
                f"Unknown objective metric '{request.objective.metric}'. "
                "Supported: funding_cost, haircut_cost, opportunity_cost"
            )
        return errors

    def prepare_problem(self, request: OptimizationRequest) -> dict[str, Any]:
        from decision_intelligence.data import load_collateral

        assets, obligations = load_collateral(request)

        # Filter ineligible assets; also exclude any assets the caller wants substituted out
        excluded_ids: set[str] = set(request.context.get("excluded_asset_ids", []))
        eligible = [a for a in assets if a.eligible and a.asset_id not in excluded_ids]
        n, m = len(eligible), len(obligations)

        # Cost vector: one variable per (asset, obligation) pair
        if request.objective.metric == "funding_cost":
            cost_per_asset = np.array([a.funding_cost_bps for a in eligible])
        elif request.objective.metric == "haircut_cost":
            cost_per_asset = np.array([a.haircut * 10_000 for a in eligible])  # normalise to bps
        else:  # opportunity_cost — proxy via funding_cost
            cost_per_asset = np.array([a.funding_cost_bps for a in eligible])

        mv = np.array([a.market_value for a in eligible])
        hc = np.array([a.haircut for a in eligible])

        # c shape: (n*m,) — cost × market_value per unit fraction
        c = np.tile(cost_per_asset * mv, m).reshape(m, n).T.ravel() / 10_000

        # Eligibility mask: eligible[i] for obligation j?
        elig_mask = np.zeros((n, m), dtype=bool)
        for j, obl in enumerate(obligations):
            for i, asset in enumerate(eligible):
                if asset.asset_class in obl.eligible_asset_classes:
                    elig_mask[i, j] = True

        # Build inequality constraints (A_ub @ x <= b_ub)
        A_ub_rows, b_ub_rows = [], []

        # (1) Inventory: Σ_j x[i,j] <= 1 for each asset i
        for i in range(n):
            row = np.zeros(n * m)
            for j in range(m):
                row[i + j * n] = 1.0
            A_ub_rows.append(row)
            b_ub_rows.append(1.0)

        # (2) Coverage (flip sign): -Σ_i x[i,j]*(1-hc[i])*mv[i] <= -required[j]
        for j, obl in enumerate(obligations):
            row = np.zeros(n * m)
            for i in range(n):
                row[i + j * n] = -(1.0 - hc[i]) * mv[i]
            A_ub_rows.append(row)
            b_ub_rows.append(-obl.required_value)

        # (4) Concentration: for each asset class, for each obligation
        conc_limit = request.context.get("concentration_limit", _CONCENTRATION_LIMIT)
        asset_classes = list({a.asset_class for a in eligible})
        for j, obl in enumerate(obligations):
            for ac in asset_classes:
                # Σ_i∈ac x[i,j]*mv[i]  <=  conc_limit * Σ_i x[i,j]*mv[i]
                # => Σ_i∈ac x[i,j]*mv[i] - conc_limit * Σ_i x[i,j]*mv[i] <= 0
                row = np.zeros(n * m)
                for i, asset in enumerate(eligible):
                    factor = mv[i] if asset.asset_class == ac else 0.0
                    factor -= conc_limit * mv[i]
                    row[i + j * n] = factor
                A_ub_rows.append(row)
                b_ub_rows.append(0.0)

        A_ub = np.array(A_ub_rows)
        b_ub = np.array(b_ub_rows)

        # Variable bounds: x[i,j] in [0, 1]; force 0 for ineligible pairs
        bounds = []
        for j in range(m):
            for i in range(n):
                if elig_mask[i, j]:
                    bounds.append((0.0, 1.0))
                else:
                    bounds.append((0.0, 0.0))

        # Baseline: naive equal-weight allocation
        baseline_value = _compute_naive_cost(eligible, obligations)

        lending_threshold = float(
            request.context.get("lending_opportunity_threshold_bps", _LENDING_OPPORTUNITY_THRESHOLD_BPS)
        )
        return {
            "assets": eligible,
            "obligations": obligations,
            "c": c,
            "A_ub": A_ub,
            "b_ub": b_ub,
            "bounds": bounds,
            "n": n,
            "m": m,
            "mv": mv,
            "hc": hc,
            "elig_mask": elig_mask,
            "baseline_value": baseline_value,
            "conc_limit": conc_limit,
            "lending_opportunity_threshold_bps": lending_threshold,
            "excluded_asset_ids": list(excluded_ids),
            "request": request,
            "solver_spec": SolverSpec.from_context(request.context),
        }

    def solve(self, problem: dict[str, Any]) -> dict[str, Any]:
        from decision_intelligence.contracts.results import SolveStatus

        lp = LinearProblem(
            c=problem["c"],
            A_ub=problem["A_ub"],
            b_ub=problem["b_ub"],
            bounds=problem["bounds"],
        )

        try:
            solver_result = solve_linear_problem(lp, problem["solver_spec"])
        except SolverConfigError as exc:
            return {"status": SolveStatus.ERROR, "message": str(exc)}

        if solver_result.status == SolveStatus.OPTIMAL and solver_result.x is not None:
            x = solver_result.x
            n = problem["n"]
            m = problem["m"]
            mv = problem["mv"]
            hc = problem["hc"]
            assets = problem["assets"]
            obligations = problem["obligations"]
            threshold = problem.get("lending_opportunity_threshold_bps", _LENDING_OPPORTUNITY_THRESHOLD_BPS)

            allocations = []
            for j, obl in enumerate(obligations):
                for i, asset in enumerate(assets):
                    frac = x[i + j * n]
                    if frac > 1e-6:
                        allocated_mv = frac * mv[i]
                        allocations.append({
                            "asset_id": asset.asset_id,
                            "label": f"{asset.label} → {obl.counterparty}",
                            "allocated_value": round(allocated_mv, 2),
                            "allocated_fraction": round(frac, 6),
                            "metadata": {
                                "obligation_id": obl.obligation_id,
                                "counterparty": obl.counterparty,
                                "asset_class": asset.asset_class,
                                "haircut": asset.haircut,
                                "funding_cost_bps": asset.funding_cost_bps,
                                "post_haircut_value": round(allocated_mv * (1 - hc[i]), 2),
                            },
                        })

            binding = _find_binding_constraints(problem, x)
            lending_opportunities = _detect_lending_opportunities(assets, x, n, m, mv, threshold)
            return {
                "status": SolveStatus.OPTIMAL,
                "objective_value": float(solver_result.objective_value or 0.0),
                "x": x,
                "allocations": allocations,
                "binding_constraints": binding,
                "metadata": solver_result.metadata,
                "lending_opportunities": lending_opportunities,
            }

        return {
            "status": solver_result.status,
            "message": solver_result.message or "Solver did not find optimal solution.",
        }

    def validate_solution(self, problem: dict[str, Any], solution: dict[str, Any]) -> list[str]:
        violations: list[str] = []
        x = solution.get("x")
        if x is None:
            return ["No solution vector available"]

        n, m = problem["n"], problem["m"]
        mv = problem["mv"]
        hc = problem["hc"]
        obligations = problem["obligations"]
        assets = problem["assets"]

        # Check coverage
        for j, obl in enumerate(obligations):
            covered = sum(x[i + j * n] * (1 - hc[i]) * mv[i] for i in range(n))
            if covered < obl.required_value * 0.9999:
                violations.append(
                    f"Obligation {obl.obligation_id} undercovered: "
                    f"${covered:,.0f} < ${obl.required_value:,.0f}"
                )

        # Check inventory
        for i, asset in enumerate(assets):
            used = sum(x[i + j * n] for j in range(m))
            if used > 1.0001:
                violations.append(
                    f"Asset {asset.asset_id} over-allocated: {used:.4f} > 1.0"
                )

        return violations

    def run_sensitivity(
        self,
        problem: dict[str, Any],
        solution: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Sensitivity: how much does objective improve if each obligation's
        required value is reduced by 10%?  (dual-price approximation via re-solve)
        """
        sensitivities = []
        obligations = problem["obligations"]
        base_obj = solution["objective_value"]

        for j, obl in enumerate(obligations):
            # Tighten this obligation by 10% and re-solve
            b_ub_mod = problem["b_ub"].copy()
            coverage_row_idx = problem["n"] + j
            delta = obl.required_value * 0.10
            b_ub_mod[coverage_row_idx] += delta  # less negative = smaller requirement

            res = linprog(
                c=problem["c"],
                A_ub=problem["A_ub"],
                b_ub=b_ub_mod,
                bounds=problem["bounds"],
                method="highs",
            )
            if res.status == 0:
                shadow = (base_obj - res.fun) / delta * 1e6  # per $1M relaxation
                sensitivities.append({
                    "parameter": f"required_value:{obl.obligation_id}",
                    "shadow_price": round(shadow, 4),
                    "range_lower": round(obl.required_value * 0.5, 0),
                    "range_upper": round(obl.required_value * 1.5, 0),
                    "interpretation": (
                        f"Reducing {obl.counterparty}'s requirement by $1M saves "
                        f"${shadow:,.2f} in funding cost"
                    ),
                })

        return sensitivities

    def explain(self, problem: dict[str, Any], solution: dict[str, Any]) -> str:
        assets = problem["assets"]
        obligations = problem["obligations"]
        obj = solution["objective_value"]
        baseline = problem["baseline_value"]
        improvement = baseline - obj
        improvement_pct = improvement / baseline * 100 if baseline else 0

        n, m = problem["n"], problem["m"]
        x = solution["x"]
        mv = problem["mv"]

        # Summarise allocation by asset class
        class_alloc: dict[str, float] = {}
        for j in range(m):
            for i, asset in enumerate(assets):
                frac = x[i + j * n]
                if frac > 1e-6:
                    class_alloc[asset.asset_class] = (
                        class_alloc.get(asset.asset_class, 0.0) + frac * mv[i]
                    )

        class_lines = "  ".join(
            f"{k}: ${v/1e6:.1f}M" for k, v in sorted(class_alloc.items())
        )

        binding = ", ".join(solution.get("binding_constraints", [])) or "none"

        threshold = problem.get("lending_opportunity_threshold_bps", _LENDING_OPPORTUNITY_THRESHOLD_BPS)
        lending_opps = solution.get("lending_opportunities") or _detect_lending_opportunities(
            assets, x, problem["n"], problem["m"], mv, threshold
        )

        lending_note = ""
        if lending_opps:
            total_lending_mv = sum(op["market_value"] for op in lending_opps)
            lending_note = (
                f"\n⚠️  Lending opportunity alert: {len(lending_opps)} high-demand asset(s) "
                f"(${total_lending_mv / 1e6:.1f}M market value) in inventory have lending rates "
                f"above {threshold:.0f} bps. Posting these as collateral forgoes that revenue. "
                "Consider sourcing substitute collateral and lending these assets instead."
            )

        return (
            f"Collateral optimizer allocated {len(assets)} eligible assets across "
            f"{len(obligations)} obligations.\n"
            f"Objective (funding cost): ${obj:,.2f} vs baseline ${baseline:,.2f} "
            f"— improvement of ${improvement:,.2f} ({improvement_pct:.1f}%).\n"
            f"Asset class mix: {class_lines}.\n"
            f"Binding constraints: {binding}."
            f"{lending_note}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_lending_opportunities(
    assets: list[CollateralAsset],
    x: np.ndarray,
    n: int,
    m: int,
    mv: np.ndarray,
    threshold_bps: float,
) -> list[dict[str, Any]]:
    """Return assets that are being posted as collateral but have high lending demand.

    An asset is flagged when its funding_cost_bps exceeds *threshold_bps* AND it has
    any nonzero allocation in the solution.  High funding cost is used as a proxy for
    high securities-lending demand (the market rebate the desk forgoes by pledging the
    asset as collateral instead of lending it out).
    """
    opportunities = []
    for i, asset in enumerate(assets):
        if asset.funding_cost_bps < threshold_bps:
            continue
        allocated_mv = sum(x[i + j * n] * mv[i] for j in range(m))
        if allocated_mv < 1e-4:
            continue
        foregone_revenue_bps = asset.funding_cost_bps
        annual_revenue_foregone = allocated_mv * foregone_revenue_bps / 10_000
        opportunities.append({
            "asset_id": asset.asset_id,
            "label": asset.label,
            "asset_class": asset.asset_class,
            "market_value": round(mv[i], 2),
            "allocated_as_collateral_value": round(allocated_mv, 2),
            "lending_rate_bps": round(asset.funding_cost_bps, 1),
            "annual_revenue_foregone": round(annual_revenue_foregone, 2),
            "message": (
                f"{asset.label} is posted as collateral but commands a "
                f"{asset.funding_cost_bps:.0f} bps lending rate — "
                f"${annual_revenue_foregone:,.0f}/yr in foregone lending revenue. "
                "Consider sourcing cheaper substitute collateral and lending this asset instead."
            ),
            "severity": "high" if asset.funding_cost_bps >= threshold_bps * 1.5 else "medium",
        })
    # Sort by foregone revenue descending
    opportunities.sort(key=lambda op: -op["annual_revenue_foregone"])
    return opportunities


def _compute_naive_cost(
    assets: list[CollateralAsset], obligations: list[CollateralObligation]
) -> float:
    """Naive baseline: allocate cheapest assets first, proportionally."""
    total_required = sum(o.required_value for o in obligations)
    total_mv = sum(a.market_value * (1 - a.haircut) for a in assets)
    if total_mv == 0:
        return 0.0
    cost = 0.0
    for a in assets:
        frac = min(1.0, total_required / max(total_mv, 1.0))
        cost += a.funding_cost_bps * a.market_value * frac / 10_000
    return cost


def _find_binding_constraints(problem: dict[str, Any], x: np.ndarray) -> list[str]:
    n, m = problem["n"], problem["m"]
    mv = problem["mv"]
    hc = problem["hc"]
    obligations = problem["obligations"]
    assets = problem["assets"]
    binding = []

    for i in range(n):
        used = sum(x[i + j * n] for j in range(m))
        if abs(used - 1.0) < 0.005:
            binding.append(f"inventory:{assets[i].asset_id}")

    for j, obl in enumerate(obligations):
        covered = sum(x[i + j * n] * (1 - hc[i]) * mv[i] for i in range(n))
        if abs(covered - obl.required_value) / (obl.required_value + 1) < 0.01:
            binding.append(f"coverage:{obl.obligation_id}")

    return binding
