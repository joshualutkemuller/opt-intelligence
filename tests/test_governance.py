"""Tests for execution-mode governance / approval enforcement."""

import pytest

from decision_intelligence.contracts import (
    ApprovalStatus,
    Objective,
    ObjectiveDirection,
    OptimizationRequest,
)
from decision_intelligence.contracts.requests import ExecutionMode
from decision_intelligence.contracts.results import SolveStatus
from decision_intelligence.governance import (
    ApprovalDecision,
    ApprovalPolicy,
    ApprovalStore,
    AuditLog,
    GovernanceController,
)
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import FinancingOptimizer


def _req(mode, portfolio="PORT_1"):
    return OptimizationRequest(
        domain="financing",
        portfolio_id=portfolio,
        objective=Objective(
            name="min_spread", direction=ObjectiveDirection.MINIMIZE, metric="funding_spread"
        ),
        execution_mode=mode,
    )


@pytest.fixture
def orch():
    audit = AuditLog()
    gov = GovernanceController(ApprovalPolicy(), ApprovalStore(), audit)
    reg = OptimizerRegistry()
    reg.register(FinancingOptimizer())
    return OptimizationOrchestrator(reg, audit, gov), audit, gov


# --------------------------------------------------------------------------- #
# Policy
# --------------------------------------------------------------------------- #
def test_policy_gates_only_state_changing_modes():
    p = ApprovalPolicy()
    assert not p.requires_approval(ExecutionMode.EXPLAIN)
    assert not p.requires_approval(ExecutionMode.RECOMMENDATION)
    assert p.requires_approval(ExecutionMode.STAGE)
    assert p.requires_approval(ExecutionMode.EXECUTE)


def test_policy_approver_allowlist():
    p = ApprovalPolicy(authorized_approvers=["alice"])
    assert p.is_authorized("alice")
    assert not p.is_authorized("bob")
    assert not p.is_authorized(None)


def test_policy_default_allows_any_named_approver():
    p = ApprovalPolicy()
    assert p.is_authorized("anyone")
    assert not p.is_authorized("")


# --------------------------------------------------------------------------- #
# Advisory tiers — auto-allowed
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "mode",
    [ExecutionMode.EXPLAIN, ExecutionMode.SCENARIO_ANALYSIS, ExecutionMode.RECOMMENDATION],
)
def test_advisory_modes_auto_allowed(orch, mode):
    orchestrator, _, _ = orch
    result = orchestrator.run(_req(mode))
    g = result.governance
    assert g is not None
    assert g.required is False
    assert g.status == ApprovalStatus.NOT_REQUIRED
    assert g.action_performed is True


# --------------------------------------------------------------------------- #
# Gated tiers — enforcement
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("mode", [ExecutionMode.STAGE, ExecutionMode.EXECUTE])
def test_gated_modes_pending_without_approval(orch, mode):
    orchestrator, _, _ = orch
    result = orchestrator.run(_req(mode))
    g = result.governance
    assert g.status == ApprovalStatus.PENDING
    assert g.required is True
    assert g.action_performed is False
    assert g.approval_id and g.approval_id.startswith("appr_")
    # the math still ran — this is a recommendation that is merely withheld
    assert result.status == SolveStatus.OPTIMAL
    assert result.allocations


def test_inline_approval_performs_action(orch):
    orchestrator, _, _ = orch
    decision = ApprovalDecision(approver="jane", granted=True, reason="ok")
    result = orchestrator.run(_req(ExecutionMode.EXECUTE), approval=decision)
    g = result.governance
    assert g.status == ApprovalStatus.APPROVED
    assert g.action_performed is True
    assert g.approver == "jane"


def test_inline_rejection_withholds_action(orch):
    orchestrator, _, _ = orch
    decision = ApprovalDecision(approver="bob", granted=False, reason="too risky")
    result = orchestrator.run(_req(ExecutionMode.STAGE), approval=decision)
    g = result.governance
    assert g.status == ApprovalStatus.REJECTED
    assert g.action_performed is False
    assert "too risky" in g.reason


def test_two_phase_submit_then_rerun(orch):
    orchestrator, _, gov = orch
    # phase 1: no decision → pending
    first = orchestrator.run(_req(ExecutionMode.EXECUTE))
    assert first.governance.status == ApprovalStatus.PENDING
    # phase 2: submit a decision, then re-run the same action
    gov.submit_decision(
        _req(ExecutionMode.EXECUTE), ApprovalDecision(approver="jane", granted=True)
    )
    second = orchestrator.run(_req(ExecutionMode.EXECUTE))
    assert second.governance.status == ApprovalStatus.APPROVED
    assert second.governance.action_performed is True


def test_unauthorized_approver_rejected():
    audit = AuditLog()
    gov = GovernanceController(
        ApprovalPolicy(authorized_approvers=["alice"]), ApprovalStore(), audit
    )
    reg = OptimizerRegistry()
    reg.register(FinancingOptimizer())
    orchestrator = OptimizationOrchestrator(reg, audit, gov)

    result = orchestrator.run(
        _req(ExecutionMode.EXECUTE),
        approval=ApprovalDecision(approver="mallory", granted=True),
    )
    g = result.governance
    assert g.status == ApprovalStatus.REJECTED
    assert g.action_performed is False
    assert "not authorized" in g.reason


def test_fingerprint_distinguishes_actions():
    store = ApprovalStore()
    fp_stage = store.fingerprint(_req(ExecutionMode.STAGE))
    fp_exec = store.fingerprint(_req(ExecutionMode.EXECUTE))
    fp_other_portfolio = store.fingerprint(_req(ExecutionMode.STAGE, portfolio="PORT_2"))
    assert fp_stage != fp_exec
    assert fp_stage != fp_other_portfolio


# --------------------------------------------------------------------------- #
# Backward compatibility — no governance controller
# --------------------------------------------------------------------------- #
def test_orchestrator_without_governance_has_no_record():
    reg = OptimizerRegistry()
    reg.register(FinancingOptimizer())
    orchestrator = OptimizationOrchestrator(reg)  # no governance
    result = orchestrator.run(_req(ExecutionMode.EXECUTE))
    assert result.governance is None
    assert result.status == SolveStatus.OPTIMAL


# --------------------------------------------------------------------------- #
# Audit trail
# --------------------------------------------------------------------------- #
def test_gated_actions_are_audited(orch):
    orchestrator, audit, _ = orch
    orchestrator.run(_req(ExecutionMode.EXECUTE), approval=ApprovalDecision("jane", True))
    events = {e.event for e in audit.all_entries()}
    assert "transaction_executed" in events
