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
from datetime import UTC, datetime
from typing import Any

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
    ExecutionMode.CHANGE_CONSTRAINTS: 5,
}
_MODE_ACTION: dict[ExecutionMode, str] = {
    ExecutionMode.EXPLAIN: "analysis",
    ExecutionMode.SCENARIO_ANALYSIS: "scenario analysis",
    ExecutionMode.RECOMMENDATION: "recommendation",
    ExecutionMode.STAGE: "stage transaction",
    ExecutionMode.EXECUTE: "execute transaction",
    ExecutionMode.CHANGE_CONSTRAINTS: "change production constraints",
}

# Audit event names recorded when a gated action is actually carried out.
_PERFORMED_EVENT: dict[ExecutionMode, str] = {
    ExecutionMode.STAGE: "transaction_staged",
    ExecutionMode.EXECUTE: "transaction_executed",
    ExecutionMode.CHANGE_CONSTRAINTS: "production_constraints_changed",
}

_MATERIAL_CONTEXT_KEYS = (
    "notional",
    "total_notional",
    "portfolio_notional",
    "total_cash",
    "total_funding_need",
    "estimated_pnl_impact",
    "governance.estimated_pnl_impact",
    "pnl_impact",
    "pnl_at_risk",
    "governance.materiality_notional",
    "production_constraint_change",
    "governance.production_constraint_change",
    "change_production_constraints",
    "changes_production_constraints",
)


@dataclass(frozen=True)
class ApprovalDecision:
    approver: str
    granted: bool
    reason: str = ""
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ApprovalThreshold:
    """Materiality threshold that can escalate a request's approval tier."""

    name: str
    context_keys: tuple[str, ...]
    threshold: float
    tier: int
    description: str = ""


@dataclass(frozen=True)
class ApprovalRequirement:
    base_tier: int
    tier: int
    action: str
    required: bool
    escalated: bool = False
    reason: str = ""
    factors: dict[str, float | str | bool] = field(default_factory=dict)


class ApprovalPolicy:
    """Decides which modes need approval and who may approve them."""

    def __init__(
        self,
        gated_modes: Iterable[ExecutionMode] = (
            ExecutionMode.STAGE,
            ExecutionMode.EXECUTE,
            ExecutionMode.CHANGE_CONSTRAINTS,
        ),
        gated_tiers: Iterable[int] = (3, 4, 5),
        thresholds: Iterable[ApprovalThreshold] = (),
        authorized_approvers: Iterable[str] | None = None,
        production_constraint_keys: Iterable[str] = (
            "production_constraint_change",
            "governance.production_constraint_change",
            "change_production_constraints",
            "changes_production_constraints",
        ),
    ) -> None:
        self.gated_modes = frozenset(gated_modes)
        self.gated_tiers = frozenset(gated_tiers)
        self.thresholds = tuple(thresholds)
        self.production_constraint_keys = tuple(production_constraint_keys)
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

    def requirement(self, request: OptimizationRequest) -> ApprovalRequirement:
        base_tier = _MODE_TIER.get(request.execution_mode, 0)
        tier = base_tier
        action = _MODE_ACTION.get(request.execution_mode, request.execution_mode.value)
        reasons: list[str] = []
        factors: dict[str, float | str | bool] = {}

        production_constraint_change = any(
            _truthy(_get_context_value(request.context, key))
            for key in self.production_constraint_keys
        )
        if production_constraint_change:
            tier = max(tier, 5)
            action = "change production constraints"
            reasons.append("production constraint change")
            factors["production_constraint_change"] = True

        for threshold in self.thresholds:
            value, key = _max_abs_context_value(request.context, threshold.context_keys)
            if value is None or value < threshold.threshold:
                continue
            tier = max(tier, threshold.tier)
            reasons.append(threshold.description or threshold.name)
            factors[threshold.name] = value
            factors[f"{threshold.name}_threshold"] = threshold.threshold
            if key:
                factors[f"{threshold.name}_source"] = key

        required = request.execution_mode in self.gated_modes or tier in self.gated_tiers
        return ApprovalRequirement(
            base_tier=base_tier,
            tier=tier,
            action=action,
            required=required,
            escalated=tier > base_tier,
            reason="; ".join(reasons),
            factors=factors,
        )


class ApprovalStore:
    """In-memory store of approval decisions keyed by a stable action fingerprint."""

    def __init__(self) -> None:
        self._decisions: dict[str, ApprovalDecision] = {}
        self._pending_ids: dict[str, str] = {}

    @staticmethod
    def fingerprint(request: OptimizationRequest) -> str:
        """Stable id for the *action*, independent of the auto-generated request_id."""
        material_context = [
            f"{key}={_get_context_value(request.context, key)}"
            for key in _MATERIAL_CONTEXT_KEYS
            if _get_context_value(request.context, key) is not None
        ]
        parts = "|".join(
            [
                request.domain,
                request.portfolio_id,
                request.execution_mode.value,
                request.objective.metric,
                request.objective.direction.value,
                *material_context,
            ]
        )
        return hashlib.sha256(parts.encode()).hexdigest()[:16]

    def approval_id(self, fingerprint: str) -> str:
        """Return (creating if needed) a stable approval id for a pending action."""
        if fingerprint not in self._pending_ids:
            self._pending_ids[fingerprint] = f"appr_{uuid.uuid4().hex[:12]}"
        return self._pending_ids[fingerprint]

    def fingerprint_for_approval_id(self, approval_id: str) -> str | None:
        for fingerprint, stored_id in self._pending_ids.items():
            if stored_id == approval_id:
                return fingerprint
        return None

    def submit(self, fingerprint: str, decision: ApprovalDecision) -> None:
        self._decisions[fingerprint] = decision

    def submit_for_approval_id(
        self,
        approval_id: str,
        decision: ApprovalDecision,
    ) -> str | None:
        fingerprint = self.fingerprint_for_approval_id(approval_id)
        if fingerprint is None:
            return None
        self.submit(fingerprint, decision)
        return fingerprint

    def get(self, fingerprint: str) -> ApprovalDecision | None:
        return self._decisions.get(fingerprint)

    def list_approvals(self) -> list[dict[str, Any]]:
        items = []
        for fingerprint, approval_id in self._pending_ids.items():
            decision = self.get(fingerprint)
            items.append(
                {
                    "approval_id": approval_id,
                    "fingerprint": fingerprint,
                    "decision": decision,
                }
            )
        return items

    def clear(self) -> None:
        self._decisions.clear()
        self._pending_ids.clear()


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
        requirement = self.policy.requirement(request)
        tier = requirement.tier
        action = requirement.action

        # Advisory tier — nothing to gate.
        if not requirement.required:
            self.audit.record(
                "governance_auto_allowed",
                request.request_id,
                {"mode": mode.value, "tier": tier, "factors": requirement.factors},
            )
            return ApprovalRecord(
                request_id=request.request_id,
                execution_mode=mode.value,
                tier=tier,
                action=action,
                required=False,
                status=ApprovalStatus.NOT_REQUIRED,
                action_performed=True,
                base_tier=requirement.base_tier,
                escalated=requirement.escalated,
                escalation_reason=requirement.reason,
                governance_factors=requirement.factors,
            )

        # Gated tier — need a decision (inline or previously stored).
        fp = self.store.fingerprint(request)
        decision = approval or self.store.get(fp)

        if decision is None:
            approval_id = self.store.approval_id(fp)
            self.audit.record(
                "approval_pending",
                request.request_id,
                {
                    "mode": mode.value,
                    "tier": tier,
                    "approval_id": approval_id,
                    "escalation_reason": requirement.reason,
                    "factors": requirement.factors,
                },
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
                base_tier=requirement.base_tier,
                escalated=requirement.escalated,
                escalation_reason=requirement.reason,
                governance_factors=requirement.factors,
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
                base_tier=requirement.base_tier,
                escalated=requirement.escalated,
                escalation_reason=requirement.reason,
                governance_factors=requirement.factors,
                decided_at=decision.decided_at,
            )

        if decision.granted:
            self.audit.record(
                _PERFORMED_EVENT.get(mode, "material_action_approved"),
                request.request_id,
                {
                    "mode": mode.value,
                    "tier": tier,
                    "approver": decision.approver,
                    "escalation_reason": requirement.reason,
                    "factors": requirement.factors,
                },
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
                base_tier=requirement.base_tier,
                escalated=requirement.escalated,
                escalation_reason=requirement.reason,
                governance_factors=requirement.factors,
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
            base_tier=requirement.base_tier,
            escalated=requirement.escalated,
            escalation_reason=requirement.reason,
            governance_factors=requirement.factors,
            decided_at=decision.decided_at,
        )


def _get_context_value(context: dict[str, Any], key: str) -> Any:
    current: Any = context
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _max_abs_context_value(
    context: dict[str, Any],
    keys: Iterable[str],
) -> tuple[float | None, str | None]:
    best_value: float | None = None
    best_key: str | None = None
    for key in keys:
        raw = _get_context_value(context, key)
        try:
            value = abs(float(raw))
        except (TypeError, ValueError):
            continue
        if best_value is None or value > best_value:
            best_value = value
            best_key = key
    return best_value, best_key
