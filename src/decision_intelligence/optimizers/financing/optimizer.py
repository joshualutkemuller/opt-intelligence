"""
Financing Optimizer

Problem: source external funding for each position at minimum total cost
(spread_bps × notional), subject to:
  - Each funding need must be fully satisfied
  - No counterparty exceeded beyond its capacity
  - Maximum single-counterparty concentration (balance sheet risk)
  - Tenor compatibility (counterparty max_tenor ≥ position required_tenor)
  - Capital usage budget (total RWA cost ≤ limit)

LP formulation:
  Variables: x[i, j] = USD amount sourced from counterparty i for need j
  Minimize:  Σ_i Σ_j  spread_bps[i] × x[i,j] / 10000
  Subject to:
    (1) Σ_i x[i,j]  = notional[j]                    (full funding per need)
    (2) Σ_j x[i,j]  ≤ capacity[i]                    (counterparty limit)
    (3) x[i,j] = 0  if tenor_incompatible             (tenor)
    (4) Σ_i Σ_j capital_pct[i] × x[i,j]  ≤ cap_budget (capital)
    (5) Σ_j x[i,j] / total_funding  ≤ max_cp_conc     (concentration)
    (6) x[i,j] ≥ 0
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

from .data import FinancingCounterparty, FundingNeed

_MAX_CP_CONCENTRATION = 0.40   # max 40% of total funding from any single counterparty
_CAPITAL_BUDGET_PCT = 5.0      # max 5% RWA cost as % of total funding


class FinancingOptimizer(OptimizationCapability):
    name = "Financing Optimizer"
    version = "0.1.0"
    domain = "financing"

    def validate_request(self, request: OptimizationRequest) -> list[str]:
        errors: list[str] = []
        if request.domain != self.domain:
            errors.append(f"Domain mismatch: expected '{self.domain}', got '{request.domain}'")
        if request.objective.metric not in ("funding_spread", "capital_usage", "funding_cost"):
            errors.append(
                f"Unknown objective metric '{request.objective.metric}'. "
                "Supported: funding_spread, capital_usage, funding_cost"
            )
        return errors

    def prepare_problem(self, request: OptimizationRequest) -> dict[str, Any]:
        from decision_intelligence.data import load_financing

        counterparties, needs = load_financing(request)

        n = len(counterparties)   # counterparties
        m = len(needs)            # funding needs
        total_funding = sum(nd.notional for nd in needs)

        ctx = request.context
        max_cp_conc = ctx.get("max_cp_concentration", _MAX_CP_CONCENTRATION)
        cap_budget_pct = ctx.get("capital_budget_pct", _CAPITAL_BUDGET_PCT)
        cap_budget = total_funding * cap_budget_pct / 100

        # Cost vector (n*m,): x[i,j] = x[i + j*n]
        if request.objective.metric == "capital_usage":
            cost_per_cp = np.array([cp.capital_usage_pct for cp in counterparties])
        else:  # funding_spread or funding_cost
            cost_per_cp = np.array([cp.spread_bps for cp in counterparties])

        c = np.tile(cost_per_cp, m).reshape(m, n).T.ravel() / 10_000

        # Tenor compatibility mask
        compat = np.zeros((n, m), dtype=bool)
        for i, cp in enumerate(counterparties):
            for j, nd in enumerate(needs):
                if (cp.min_tenor_days <= nd.required_tenor_days <= cp.max_tenor_days):
                    compat[i, j] = True

        A_ub_rows, b_ub_rows = [], []

        # (2) Counterparty capacity: Σ_j x[i,j] ≤ capacity[i]
        for i, cp in enumerate(counterparties):
            row = np.zeros(n * m)
            for j in range(m):
                row[i + j * n] = 1.0
            A_ub_rows.append(row)
            b_ub_rows.append(cp.capacity)

        # (4) Capital budget: Σ_i Σ_j capital_pct[i]/100 × x[i,j] ≤ cap_budget
        cap_row = np.zeros(n * m)
        for i, cp in enumerate(counterparties):
            for j in range(m):
                cap_row[i + j * n] = cp.capital_usage_pct / 100
        A_ub_rows.append(cap_row)
        b_ub_rows.append(cap_budget)

        # (5) Concentration: Σ_j x[i,j] ≤ max_cp_conc × total_funding
        for i, cp in enumerate(counterparties):
            row = np.zeros(n * m)
            for j in range(m):
                row[i + j * n] = 1.0
            A_ub_rows.append(row)
            b_ub_rows.append(max_cp_conc * total_funding)

        A_ub = np.array(A_ub_rows)
        b_ub = np.array(b_ub_rows)

        # Equality: Σ_i x[i,j] = notional[j]
        A_eq = np.zeros((m, n * m))
        b_eq = np.array([nd.notional for nd in needs])
        for j in range(m):
            for i in range(n):
                A_eq[j, i + j * n] = 1.0

        # Bounds: 0 if tenor incompatible, else (0, capacity[i])
        bounds = []
        for j in range(m):
            for i, cp in enumerate(counterparties):
                if compat[i, j]:
                    bounds.append((0.0, cp.capacity))
                else:
                    bounds.append((0.0, 0.0))

        baseline_value = _compute_naive_cost(counterparties, needs)

        return {
            "counterparties": counterparties,
            "needs": needs,
            "c": c,
            "A_ub": A_ub,
            "b_ub": b_ub,
            "A_eq": A_eq,
            "b_eq": b_eq,
            "bounds": bounds,
            "n": n,
            "m": m,
            "compat": compat,
            "total_funding": total_funding,
            "cap_budget": cap_budget,
            "max_cp_conc": max_cp_conc,
            "baseline_value": baseline_value,
            "solver_spec": SolverSpec.from_context(request.context),
        }

    def solve(self, problem: dict[str, Any]) -> dict[str, Any]:
        from decision_intelligence.contracts.results import SolveStatus

        lp = LinearProblem(
            c=problem["c"],
            A_ub=problem["A_ub"],
            b_ub=problem["b_ub"],
            A_eq=problem["A_eq"],
            b_eq=problem["b_eq"],
            bounds=problem["bounds"],
        )

        try:
            solver_result = solve_linear_problem(lp, problem["solver_spec"])
        except SolverConfigError as exc:
            return {"status": SolveStatus.ERROR, "message": str(exc)}

        if solver_result.status == SolveStatus.OPTIMAL and solver_result.x is not None:
            x = solver_result.x
            n, m = problem["n"], problem["m"]
            cps = problem["counterparties"]
            needs = problem["needs"]

            allocations = []
            for j, nd in enumerate(needs):
                for i, cp in enumerate(cps):
                    amt = x[i + j * n]
                    if amt > 1.0:
                        allocations.append({
                            "asset_id": cp.counterparty_id,
                            "label": f"{cp.name} ({cp.instrument}) → {nd.position_id}",
                            "allocated_value": round(amt, 2),
                            "allocated_fraction": round(amt / nd.notional, 6),
                            "metadata": {
                                "position_id": nd.position_id,
                                "counterparty": cp.name,
                                "instrument": cp.instrument,
                                "spread_bps": cp.spread_bps,
                                "capital_usage_pct": cp.capital_usage_pct,
                                "tenor_days": nd.required_tenor_days,
                                "cost_usd": round(amt * cp.spread_bps / 10_000, 2),
                            },
                        })

            binding = _find_binding(problem, x)
            return {
                "status": SolveStatus.OPTIMAL,
                "objective_value": float(solver_result.objective_value or 0.0),
                "x": x,
                "allocations": allocations,
                "binding_constraints": binding,
                "metadata": {
                    **solver_result.metadata,
                    "n_counterparties_used": int((
                        np.array([sum(x[i + j * n] for j in range(m)) for i in range(n)]) > 1.0
                    ).sum()),
                },
            }

        return {
            "status": solver_result.status,
            "message": solver_result.message or "Solver did not find optimal solution.",
        }

    def validate_solution(self, problem: dict[str, Any], solution: dict[str, Any]) -> list[str]:
        violations: list[str] = []
        x = solution.get("x")
        if x is None:
            return ["No solution vector"]

        n, m = problem["n"], problem["m"]
        cps = problem["counterparties"]
        needs = problem["needs"]

        # Coverage
        for j, nd in enumerate(needs):
            sourced = sum(x[i + j * n] for i in range(n))
            if abs(sourced - nd.notional) > nd.notional * 0.001:
                violations.append(
                    f"Need {nd.position_id} underfunded: ${sourced:,.0f} vs ${nd.notional:,.0f}"
                )

        # Capacity
        for i, cp in enumerate(cps):
            used = sum(x[i + j * n] for j in range(m))
            if used > cp.capacity * 1.001:
                violations.append(
                    f"Counterparty {cp.counterparty_id} over-capacity: "
                    f"${used:,.0f} > ${cp.capacity:,.0f}"
                )

        return violations

    def run_sensitivity(
        self,
        problem: dict[str, Any],
        solution: dict[str, Any],
    ) -> list[dict[str, Any]]:
        base_obj = solution["objective_value"]
        sensitivities = []

        for i, cp in enumerate(problem["counterparties"]):
            b_mod = problem["b_ub"].copy()
            delta = cp.capacity * 0.25
            b_mod[i] += delta  # expand this counterparty's capacity by 25%

            res = linprog(
                c=problem["c"],
                A_ub=problem["A_ub"],
                b_ub=b_mod,
                A_eq=problem["A_eq"],
                b_eq=problem["b_eq"],
                bounds=problem["bounds"],
                method="highs",
            )
            if res.status == 0 and abs(res.fun - base_obj) > 0.01:
                saving = base_obj - res.fun
                sensitivities.append({
                    "parameter": f"capacity:{cp.counterparty_id}",
                    "shadow_price": round(saving / delta * 1e6, 4),
                    "range_lower": round(cp.capacity * 0.5, 0),
                    "range_upper": round(cp.capacity * 1.5, 0),
                    "interpretation": (
                        f"Increasing {cp.name} capacity by $1M saves ${saving/delta*1e6:,.2f} "
                        f"in financing spread"
                    ),
                })

        return sorted(sensitivities, key=lambda s: -s["shadow_price"])[:5]

    def explain(self, problem: dict[str, Any], solution: dict[str, Any]) -> str:
        cps = problem["counterparties"]
        x = solution["x"]
        n, m = problem["n"], problem["m"]

        obj = solution["objective_value"]
        baseline = problem["baseline_value"]
        improvement = baseline - obj
        improvement_pct = improvement / baseline * 100 if baseline else 0

        # Summarise by instrument
        instr_alloc: dict[str, float] = {}
        for j in range(m):
            for i, cp in enumerate(cps):
                amt = x[i + j * n]
                if amt > 1.0:
                    instr_alloc[cp.instrument] = instr_alloc.get(cp.instrument, 0.0) + amt

        instr_lines = "  ".join(f"{k}: ${v/1e6:.1f}M" for k, v in sorted(instr_alloc.items()))

        n_cps_used = int(
            sum(1 for i in range(n) if sum(x[i + j * n] for j in range(m)) > 1.0)
        )
        binding = ", ".join(solution.get("binding_constraints", [])) or "none"

        return (
            f"Financing optimizer sourced ${problem['total_funding']/1e6:.0f}M across "
            f"{n_cps_used} counterparties.\n"
            f"Objective (financing spread cost): ${obj:,.2f} vs baseline ${baseline:,.2f} "
            f"— improvement of ${improvement:,.2f} ({improvement_pct:.1f}%).\n"
            f"Instrument mix: {instr_lines}.\n"
            f"Binding constraints: {binding}.\n"
            f"The optimizer preferred lower-spread repo counterparties for longer tenors "
            f"and routed short-tenor needs to the cheapest available source."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_naive_cost(
    cps: list[FinancingCounterparty], needs: list[FundingNeed]
) -> float:
    total = sum(nd.notional for nd in needs)
    if not cps:
        return 0.0
    avg_spread = sum(cp.spread_bps for cp in cps) / len(cps)
    return total * avg_spread / 10_000


def _find_binding(problem: dict[str, Any], x: np.ndarray) -> list[str]:
    n, m = problem["n"], problem["m"]
    cps = problem["counterparties"]
    binding = []
    tol = 0.01

    for i, cp in enumerate(cps):
        used = sum(x[i + j * n] for j in range(m))
        if abs(used - cp.capacity) / (cp.capacity + 1) < tol and used > 1.0:
            binding.append(f"capacity:{cp.counterparty_id}")

    total_funding = problem["total_funding"]
    for i, cp in enumerate(cps):
        used = sum(x[i + j * n] for j in range(m))
        if abs(used - problem["max_cp_conc"] * total_funding) / (total_funding + 1) < tol:
            binding.append(f"concentration:{cp.counterparty_id}")

    # Capital
    cap_used = sum(
        x[i + j * n] * cps[i].capital_usage_pct / 100
        for i in range(n)
        for j in range(m)
    )
    if abs(cap_used - problem["cap_budget"]) / (problem["cap_budget"] + 1) < tol:
        binding.append("capital_budget")

    return binding
