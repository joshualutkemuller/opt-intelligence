"""Tests for structured optimization validation reports."""

from decision_intelligence.contracts import (
    AllocationItem,
    Objective,
    ObjectiveDirection,
    OptimizationRequest,
)
from decision_intelligence.contracts.requests import ExecutionMode
from decision_intelligence.contracts.results import (
    OptimizationResult,
    SolveStatus,
    ValidationResult,
)
from decision_intelligence.governance import (
    ApprovalPolicy,
    ApprovalStore,
    AuditLog,
    GovernanceController,
)
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import FinancingOptimizer, MoneyMarketOptimizer
from decision_intelligence.validation import apply_validation_report


def _money_market_request() -> OptimizationRequest:
    return OptimizationRequest(
        domain="money_market",
        portfolio_id="PORT_001",
        objective=Objective(
            name="max_yield",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="yield",
        ),
        context={"seed": 42},
    )


def test_validation_report_attached_to_orchestrated_result():
    registry = OptimizerRegistry()
    registry.register(MoneyMarketOptimizer())
    orchestrator = OptimizationOrchestrator(registry)

    result = orchestrator.run(_money_market_request())

    report = result.validation_report
    assert report is not None
    assert report.passed is True
    assert report.recommendation == "ready"
    assert result.validation.passed is True
    assert any(check.name == "allocation_fractions" for check in report.checks)
    assert report.data_quality["allocation_count"] == len(result.allocations)


def test_validation_report_marks_pending_governance_for_review():
    audit = AuditLog()
    governance = GovernanceController(ApprovalPolicy(), ApprovalStore(), audit)
    registry = OptimizerRegistry()
    registry.register(FinancingOptimizer())
    orchestrator = OptimizationOrchestrator(registry, audit, governance)
    request = OptimizationRequest(
        domain="financing",
        portfolio_id="PORT_001",
        objective=Objective(
            name="min_spread",
            direction=ObjectiveDirection.MINIMIZE,
            metric="funding_spread",
        ),
        execution_mode=ExecutionMode.EXECUTE,
        context={"seed": 42},
    )

    result = orchestrator.run(request)

    report = result.validation_report
    assert report is not None
    assert report.passed is True
    assert report.recommendation == "review"
    assert report.policy_status == "pending"
    assert "Governance approval is pending" in report.warnings[0]
    assert result.validation.warnings


def test_validation_report_blocks_invalid_allocations():
    result = OptimizationResult(
        request_id="bad-alloc",
        domain="money_market",
        status=SolveStatus.OPTIMAL,
        objective_value=1.0,
        baseline_value=0.9,
        improvement=0.1,
        improvement_pct=11.1,
        allocations=[
            AllocationItem(
                asset_id="A",
                label="Bad allocation",
                allocated_value=-100.0,
                allocated_fraction=-0.1,
            )
        ],
        validation=ValidationResult(passed=True),
        explanation="bad allocation fixture",
    )

    result = apply_validation_report(result)

    assert result.validation_report is not None
    assert result.validation_report.passed is False
    assert result.validation_report.recommendation == "blocked"
    assert any("negative" in violation for violation in result.validation.violations)
