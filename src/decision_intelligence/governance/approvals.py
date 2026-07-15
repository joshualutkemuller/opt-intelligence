"""
Execution-mode governance — enforce human-approval levels.

The optimization math runs the same regardless of execution mode; what this
layer governs is whether the *action* the mode implies is allowed to proceed:

* Advisory tiers — explain / scenario_analysis / recommendation — are
  auto-allowed (``NOT_REQUIRED``).
* State-changing tiers — stage / execute — are gated: the action is withheld
  (``PENDING``) until an authorized approver grants it, at which point it is
  performed (``APPROVED``) or refused (``REJECTED``).

A :class:`GovernanceController` ties a policy, an approval store, and the audit
log together and produces an immutable :class:`ApprovalRecord` for each request.

Two ways to supply approval:

* **Inline** — pass an :class:`ApprovalDecision` to ``evaluate`` (one-shot; used
  by the CLI's ``--approve-as``).
* **Two-phase** — call :meth:`GovernanceController.submit_decision` first, then
  re-run the request; the stored decision is matched by a stable fingerprint of
  the action (domain, portfolio, mode, objective).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from decision_intelligence.contracts import (
    ApprovalRecord,
    ApprovalStatus,
    OptimizationRequest,
)
from decision_intelligence.contracts.requests import ExecutionMode
from decision_intelligence.governance.audit import AuditLog

# Execution mode → (approval tier, human-readable action).
_MODE_TIER: dict[ExecutionMode, int] = {
    ExecutionMode.EXPLAIN: 0,
    ExecutionMode.SCENARIO_ANALYSIS: 1,
    ExecutionMode.RECOMMENDATION: 2,
    ExecutionMode.STAGE: 3,
    ExecutionMode.EXECUTE: 4,
}
_MODE_ACTION: dict[ExecutionMode, str] = {
    ExecutionMode.EXPLAIN: "analysis",
    ExecutionMode.SCENARIO_ANALYSIS: "scenario analysis",
    ExecutionMode.RECOMMENDATION: "recommendation",
    ExecutionMode.STAGE: "stage transaction",
    ExecutionMode.EXECUTE: "execute transaction",
}

# Audit event names recorded when a gated action is actually carried out.
_PERFORMED_EVENT: dict[ExecutionMode, str] = {
    ExecutionMode.STAGE: "transaction_staged",
    ExecutionMode.EXECUTE: "transaction_executed",
}


@dataclass(frozen=True)
class ApprovalDecision:
    approver: str
    granted: bool
    reason: str = ""
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalPolicy:
    """Decides which modes need approval and who may approve them."""

    def __init__(
        self,
        gated_modes: Iterable[ExecutionMode] = (ExecutionMode.STAGE, ExecutionMode.EXECUTE),
        authorized_approvers: Iterable[str] | None = None,
    ) -> None:
        self.gated_modes = frozenset(gated_modes)
        # None → any non-empty approver is allowed (POC default).
        self.authorized_approvers = (
            frozenset(authorized_approvers) if authorized_approvers is not None else None
        )

    def requires_approval(self, mode: ExecutionMode) -> bool:
        return mode in self.gated_modes

    def is_authorized(self, approver: str | None) -> bool:
        if not approver:
            return False
        if self.authorized_approvers is None:
            return True
        return approver in self.authorized_approvers


class ApprovalStore:
    """In-memory store of approval decisions keyed by a stable action fingerprint."""

    def __init__(self) -> None:
        self._decisions: dict[str, ApprovalDecision] = {}
        self._pending_ids: dict[str, str] = {}

    @staticmethod
    def fingerprint(request: OptimizationRequest) -> str:
        """Stable id for the *action*, independent of the auto-generated request_id."""
        parts = "|".join(
            [
                request.domain,
                request.portfolio_id,
                request.execution_mode.value,
                request.objective.metric,
                request.objective.direction.value,
            ]
        )
        return hashlib.sha256(parts.encode()).hexdigest()[:16]

    def approval_id(self, fingerprint: str) -> str:
        """Return (creating if needed) a stable approval id for a pending action."""
        if fingerprint not in self._pending_ids:
            self._pending_ids[fingerprint] = f"appr_{uuid.uuid4().hex[:12]}"
        return self._pending_ids[fingerprint]

    def submit(self, fingerprint: str, decision: ApprovalDecision) -> None:
        self._decisions[fingerprint] = decision

    def get(self, fingerprint: str) -> ApprovalDecision | None:
        return self._decisions.get(fingerprint)


class GovernanceController:
    """Applies an ApprovalPolicy to requests and records outcomes to the audit log."""

    def __init__(
        self,
        policy: ApprovalPolicy | None = None,
        store: ApprovalStore | None = None,
        audit: AuditLog | None = None,
    ) -> None:
        self.policy = policy or ApprovalPolicy()
        self.store = store or ApprovalStore()
        self.audit = audit or AuditLog()

    def submit_decision(
        self, request: OptimizationRequest, decision: ApprovalDecision
    ) -> str:
        """Record a decision for later matching (two-phase flow). Returns the fingerprint."""
        fp = self.store.fingerprint(request)
        self.store.submit(fp, decision)
        self.audit.record(
            "approval_decision_submitted",
            request.request_id,
            {
                "fingerprint": fp,
                "approver": decision.approver,
                "granted": decision.granted,
            },
        )
        return fp

    def evaluate(
        self,
        request: OptimizationRequest,
        approval: ApprovalDecision | None = None,
    ) -> ApprovalRecord:
        """Produce the governance record for a request, enforcing the policy."""
        mode = request.execution_mode
        tier = _MODE_TIER.get(mode, 0)
        action = _MODE_ACTION.get(mode, mode.value)

        # Advisory tier — nothing to gate.
        if not self.policy.requires_approval(mode):
            self.audit.record(
                "governance_auto_allowed",
                request.request_id,
                {"mode": mode.value, "tier": tier},
            )
            return ApprovalRecord(
                request_id=request.request_id,
                execution_mode=mode.value,
                tier=tier,
                action=action,
                required=False,
                status=ApprovalStatus.NOT_REQUIRED,
                action_performed=True,
            )

        # Gated tier — need a decision (inline or previously stored).
        fp = self.store.fingerprint(request)
        decision = approval or self.store.get(fp)

        if decision is None:
            approval_id = self.store.approval_id(fp)
            self.audit.record(
                "approval_pending",
                request.request_id,
                {"mode": mode.value, "tier": tier, "approval_id": approval_id},
            )
            return ApprovalRecord(
                request_id=request.request_id,
                execution_mode=mode.value,
                tier=tier,
                action=action,
                required=True,
                status=ApprovalStatus.PENDING,
                action_performed=False,
                approval_id=approval_id,
            )

        # Reject decisions from unauthorized approvers.
        if decision.granted and not self.policy.is_authorized(decision.approver):
            self.audit.record(
                "approval_unauthorized",
                request.request_id,
                {"mode": mode.value, "approver": decision.approver},
            )
            return ApprovalRecord(
                request_id=request.request_id,
                execution_mode=mode.value,
                tier=tier,
                action=action,
                required=True,
                status=ApprovalStatus.REJECTED,
                action_performed=False,
                approver=decision.approver,
                reason=f"Approver '{decision.approver}' is not authorized for tier {tier}.",
                decided_at=decision.decided_at,
            )

        if decision.granted:
            self.audit.record(
                _PERFORMED_EVENT.get(mode, "action_performed"),
                request.request_id,
                {"mode": mode.value, "tier": tier, "approver": decision.approver},
            )
            return ApprovalRecord(
                request_id=request.request_id,
                execution_mode=mode.value,
                tier=tier,
                action=action,
                required=True,
                status=ApprovalStatus.APPROVED,
                action_performed=True,
                approver=decision.approver,
                reason=decision.reason,
                decided_at=decision.decided_at,
            )

        # Explicit rejection.
        self.audit.record(
            "approval_rejected",
            request.request_id,
            {"mode": mode.value, "tier": tier, "approver": decision.approver},
        )
        return ApprovalRecord(
            request_id=request.request_id,
            execution_mode=mode.value,
            tier=tier,
            action=action,
            required=True,
            status=ApprovalStatus.REJECTED,
            action_performed=False,
            approver=decision.approver,
            reason=decision.reason or "Rejected by approver.",
            decided_at=decision.decided_at,
        )
