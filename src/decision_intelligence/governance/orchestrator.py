"""GovernanceOrchestrator — auto-route requests to the correct approval tier.

The orchestrator inspects a workflow result or a direct optimization request,
determines the required approval tier by materiality and execution mode, and
manages the two-phase approval flow for tiers 3-5.  Advisory tiers 0-2 are
auto-allowed and returned immediately.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from decision_intelligence.contracts import ApprovalStatus, OptimizationRequest
from decision_intelligence.contracts.requests import ExecutionMode

from .approvals import (
    ApprovalDecision,
    ApprovalPolicy,
    ApprovalStore,
    ApprovalThreshold,
    GovernanceController,
)
from .audit import AuditLog


@dataclass(frozen=True)
class RoutingDecision:
    """Result of routing a request through the governance orchestrator."""

    request_id: str
    domain: str
    portfolio_id: str
    execution_mode: str
    base_tier: int
    tier: int
    action: str
    required: bool
    escalated: bool
    escalation_reason: str
    governance_factors: dict[str, Any]
    status: str  # "auto_allowed" | "pending" | "approved" | "rejected"
    approval_id: str | None
    action_performed: bool
    routed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "domain": self.domain,
            "portfolio_id": self.portfolio_id,
            "execution_mode": self.execution_mode,
            "base_tier": self.base_tier,
            "tier": self.tier,
            "action": self.action,
            "required": self.required,
            "escalated": self.escalated,
            "escalation_reason": self.escalation_reason,
            "governance_factors": self.governance_factors,
            "status": self.status,
            "approval_id": self.approval_id,
            "action_performed": self.action_performed,
            "routed_at": self.routed_at,
        }


@dataclass(frozen=True)
class AdvanceResult:
    """Result of advancing a pending approval (approve or reject)."""

    approval_id: str
    fingerprint: str
    status: str  # "approved" | "rejected"
    approver: str
    reason: str
    tier: int
    action_performed: bool
    decided_at: str


class GovernanceOrchestrator:
    """Auto-route requests to the correct approval tier and manage two-phase flow.

    Usage::

        orch = GovernanceOrchestrator(policy, store, audit)
        decision = orch.route(request)         # determines tier; issues approval_id if gated
        advance = orch.advance(                # approver submits decision
            approval_id=decision.approval_id,
            approver="jane.doe",
            granted=True,
            reason="within limits",
        )
        # Re-run the request — GovernanceController will find the stored decision.
    """

    def __init__(
        self,
        policy: ApprovalPolicy | None = None,
        store: ApprovalStore | None = None,
        audit: AuditLog | None = None,
    ) -> None:
        self.policy = policy or _default_policy()
        self.store = store or ApprovalStore()
        self.audit = audit or AuditLog()
        self._controller = GovernanceController(self.policy, self.store, self.audit)

    def route(self, request: OptimizationRequest) -> RoutingDecision:
        """Inspect the request, determine the required tier, and issue an approval_id if gated."""
        requirement = self.policy.requirement(request)
        tier = requirement.tier
        base_tier = requirement.base_tier

        if not requirement.required:
            self.audit.record(
                "orchestrator_auto_allowed",
                request.request_id,
                {"mode": request.execution_mode.value, "tier": tier},
            )
            return RoutingDecision(
                request_id=request.request_id,
                domain=request.domain,
                portfolio_id=request.portfolio_id,
                execution_mode=request.execution_mode.value,
                base_tier=base_tier,
                tier=tier,
                action=requirement.action,
                required=False,
                escalated=requirement.escalated,
                escalation_reason=requirement.reason,
                governance_factors=dict(requirement.factors),
                status="auto_allowed",
                approval_id=None,
                action_performed=True,
            )

        fp = self.store.fingerprint(request)
        existing = self.store.get(fp)
        if existing is not None:
            status = "approved" if existing.granted else "rejected"
            return RoutingDecision(
                request_id=request.request_id,
                domain=request.domain,
                portfolio_id=request.portfolio_id,
                execution_mode=request.execution_mode.value,
                base_tier=base_tier,
                tier=tier,
                action=requirement.action,
                required=True,
                escalated=requirement.escalated,
                escalation_reason=requirement.reason,
                governance_factors=dict(requirement.factors),
                status=status,
                approval_id=self.store.approval_id(fp),
                action_performed=existing.granted,
            )

        approval_id = self.store.approval_id(fp)
        self.audit.record(
            "orchestrator_gate_issued",
            request.request_id,
            {
                "mode": request.execution_mode.value,
                "tier": tier,
                "approval_id": approval_id,
                "escalation_reason": requirement.reason,
                "factors": requirement.factors,
            },
        )
        return RoutingDecision(
            request_id=request.request_id,
            domain=request.domain,
            portfolio_id=request.portfolio_id,
            execution_mode=request.execution_mode.value,
            base_tier=base_tier,
            tier=tier,
            action=requirement.action,
            required=True,
            escalated=requirement.escalated,
            escalation_reason=requirement.reason,
            governance_factors=dict(requirement.factors),
            status="pending",
            approval_id=approval_id,
            action_performed=False,
        )

    def route_workflow(
        self,
        workflow_result: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Route based on the highest-materiality step from a workflow result dict."""
        request = _synthetic_request_from_workflow(workflow_result, context or {})
        return self.route(request)

    def advance(
        self,
        approval_id: str,
        *,
        approver: str,
        granted: bool,
        reason: str = "",
    ) -> AdvanceResult:
        """Submit an approval/rejection decision for a pending gate."""
        fp = self.store.fingerprint_for_approval_id(approval_id)
        if fp is None:
            raise ValueError(f"Unknown approval_id: {approval_id}")

        decision = ApprovalDecision(
            approver=approver,
            granted=granted,
            reason=reason,
        )
        self.store.submit(fp, decision)
        status = "approved" if granted else "rejected"

        # Determine tier for this fingerprint from any request still routed to it.
        self.audit.record(
            f"orchestrator_{status}",
            approval_id,
            {"approver": approver, "reason": reason, "fingerprint": fp},
        )
        return AdvanceResult(
            approval_id=approval_id,
            fingerprint=fp,
            status=status,
            approver=approver,
            reason=reason,
            tier=self._tier_from_fingerprint(fp),
            action_performed=granted,
            decided_at=decision.decided_at.isoformat(),
        )

    def pending(self) -> list[dict[str, Any]]:
        """Return all pending (undecided) approval items."""
        result = []
        for item in self.store.list_approvals():
            decision = item.get("decision")
            if decision is None:
                result.append(
                    {
                        "approval_id": item["approval_id"],
                        "fingerprint": item["fingerprint"],
                        "status": "pending",
                    }
                )
        return result

    def _tier_from_fingerprint(self, fingerprint: str) -> int:
        for item in self.store.list_approvals():
            if item["fingerprint"] == fingerprint:
                return 3  # conservative default if we can't recover the request
        return 3


def _default_policy() -> ApprovalPolicy:
    return ApprovalPolicy(
        thresholds=[
            ApprovalThreshold(
                name="large_notional",
                context_keys=(
                    "governance.materiality_notional",
                    "materiality_notional",
                    "notional",
                    "total_funding_need",
                    "portfolio_notional",
                ),
                threshold=1_000_000_000,
                tier=4,
                description="notional exposure exceeds $1B",
            ),
            ApprovalThreshold(
                name="pnl_impact",
                context_keys=(
                    "governance.estimated_pnl_impact",
                    "estimated_pnl_impact",
                    "pnl_impact",
                    "pnl_at_risk",
                ),
                threshold=5_000_000,
                tier=4,
                description="estimated PnL impact exceeds $5M",
            ),
        ]
    )


def _synthetic_request_from_workflow(
    workflow_result: dict[str, Any],
    extra_context: dict[str, Any],
) -> OptimizationRequest:
    """Build a synthetic OptimizationRequest from a workflow result dict for routing."""
    from decision_intelligence.contracts import Objective, ObjectiveDirection

    result = _record(workflow_result.get("result") or workflow_result)
    steps = [_record(s) for s in _list(result.get("step_results"))]
    final_step = steps[-1] if steps else {}
    final_req = _record(final_step.get("request"))
    context = {**_record(final_req.get("context")), **extra_context}

    portfolio_id = (
        final_req.get("portfolio_id")
        or _record(workflow_result.get("payload")).get("portfolio_id")
        or "PORT_001"
    )
    domain = final_step.get("domain") or result.get("workflow_id") or "workflow"

    # Determine the highest execution mode seen across steps.
    mode_rank = {m.value: i for i, m in enumerate(ExecutionMode)}
    best_mode = ExecutionMode.RECOMMENDATION
    for step in steps:
        step_req = _record(step.get("request"))
        raw_mode = step_req.get("execution_mode")
        if raw_mode and raw_mode in mode_rank:
            candidate = ExecutionMode(raw_mode)
            if mode_rank[candidate.value] > mode_rank[best_mode.value]:
                best_mode = candidate

    return OptimizationRequest(
        domain=domain,
        portfolio_id=portfolio_id,
        objective=Objective(
            name="workflow_objective",
            direction=ObjectiveDirection.MAXIMIZE,
            metric="workflow",
        ),
        execution_mode=best_mode,
        context=context,
        requestor="governance_orchestrator",
    )


def _record(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []
