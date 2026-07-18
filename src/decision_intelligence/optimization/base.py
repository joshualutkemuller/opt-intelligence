"""Common interface every optimization capability must implement."""

from abc import ABC, abstractmethod
from typing import Any

from decision_intelligence.contracts import OptimizationRequest, OptimizationResult


class OptimizationCapability(ABC):
    """
    Base class for all optimization domains.

    Lifecycle:
        validate_request → prepare_problem → solve → validate_solution
        → run_sensitivity → explain → build_result
    """

    name: str
    version: str
    domain: str

    @abstractmethod
    def validate_request(self, request: OptimizationRequest) -> list[str]:
        """Return a list of validation error strings (empty = valid)."""

    @abstractmethod
    def prepare_problem(self, request: OptimizationRequest) -> dict[str, Any]:
        """
        Load/simulate data and build the LP/optimization problem representation.
        Returns a domain-specific problem dict consumed by solve().
        """

    @abstractmethod
    def solve(self, problem: dict[str, Any]) -> dict[str, Any]:
        """
        Run the mathematical optimization.
        Returns a solution dict with at minimum: status, objective_value, allocations.
        """

    @abstractmethod
    def validate_solution(
        self, problem: dict[str, Any], solution: dict[str, Any]
    ) -> list[str]:
        """Return constraint violations found in the solution (empty = clean)."""

    def run_sensitivity(
        self, problem: dict[str, Any], solution: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Return sensitivity/shadow-price analysis. Override for domain detail."""
        return []

    @abstractmethod
    def explain(self, problem: dict[str, Any], solution: dict[str, Any]) -> str:
        """Produce a natural-language explanation of the recommendation."""

    def run(self, request: OptimizationRequest) -> OptimizationResult:
        """Full optimization lifecycle — orchestrator calls this."""
        from decision_intelligence.contracts import (
            AllocationItem,
            OptimizationResult,
            SensitivityItem,
            SolveStatus,
            ValidationResult,
        )

        errors = self.validate_request(request)
        if errors:
            return OptimizationResult(
                request_id=request.request_id,
                domain=self.domain,
                status=SolveStatus.ERROR,
                objective_value=0.0,
                baseline_value=0.0,
                improvement=0.0,
                improvement_pct=0.0,
                validation=ValidationResult(passed=False, violations=errors),
                explanation=f"Request validation failed: {'; '.join(errors)}",
            )

        problem = self.prepare_problem(request)
        solution = self.solve(problem)

        status = SolveStatus(solution.get("status", SolveStatus.ERROR))
        if status != SolveStatus.OPTIMAL:
            return OptimizationResult(
                request_id=request.request_id,
                domain=self.domain,
                status=status,
                objective_value=0.0,
                baseline_value=problem.get("baseline_value", 0.0),
                improvement=0.0,
                improvement_pct=0.0,
                explanation=solution.get("message", "Solver did not find optimal solution."),
            )

        violations = self.validate_solution(problem, solution)
        sensitivities_raw = self.run_sensitivity(problem, solution)
        explanation = self.explain(problem, solution)

        baseline = problem.get("baseline_value", 0.0)
        obj_val = solution["objective_value"]
        improvement = (
            baseline - obj_val
            if request.objective.direction.value == "minimize"
            else obj_val - baseline
        )
        improvement_pct = (improvement / abs(baseline) * 100) if baseline != 0 else 0.0

        allocations = [
            AllocationItem(**a) for a in solution.get("allocations", [])
        ]
        sensitivities = [SensitivityItem(**s) for s in sensitivities_raw]

        return OptimizationResult(
            request_id=request.request_id,
            domain=self.domain,
            status=status,
            objective_value=obj_val,
            baseline_value=baseline,
            improvement=improvement,
            improvement_pct=improvement_pct,
            allocations=allocations,
            binding_constraints=solution.get("binding_constraints", []),
            sensitivities=sensitivities,
            validation=ValidationResult(
                passed=len(violations) == 0,
                violations=violations,
            ),
            explanation=explanation,
            solver_metadata=solution.get("metadata", {}),
        )
