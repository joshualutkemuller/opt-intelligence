"""Tests for workflow audit narrative generation."""

from decision_intelligence.governance import build_workflow_audit_narrative
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    AssetAllocationMVOOptimizer,
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)
from decision_intelligence.workflows import (
    DEFAULT_WORKFLOW_REGISTRY,
    LIQUIDITY_STRESS_WORKFLOW_ID,
    SequentialWorkflowRunner,
)


def test_workflow_audit_narrative_contains_compliance_sections():
    registry = OptimizerRegistry()
    registry.register(AssetAllocationMVOOptimizer())
    registry.register(CollateralOptimizer())
    registry.register(MoneyMarketOptimizer())
    registry.register(FinancingOptimizer())
    plan = DEFAULT_WORKFLOW_REGISTRY.build(
        LIQUIDITY_STRESS_WORKFLOW_ID,
        portfolio_id="PORT_AUDIT",
        seed=7,
    )
    result = SequentialWorkflowRunner(OptimizationOrchestrator(registry)).run(plan)

    narrative = build_workflow_audit_narrative(
        response={
            "plan": plan.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
        },
        payload={"workflow": LIQUIDITY_STRESS_WORKFLOW_ID, "portfolio_id": "PORT_AUDIT"},
        preset={"preset_id": "audit_demo"},
    )

    assert narrative.title.startswith("Audit Narrative")
    assert "PORT_AUDIT" in narrative.decision_summary
    assert narrative.constraint_context
    assert narrative.approval_chain
    assert narrative.risk_flags
    assert narrative.timeline
    assert "## Approval Chain" in narrative.markdown
    assert narrative.json_payload["workflow_id"] == LIQUIDITY_STRESS_WORKFLOW_ID
