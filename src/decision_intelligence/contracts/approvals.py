"""
Approval / execution-mode governance contracts.

The platform's :class:`ExecutionMode` tiers map to the human-approval levels in
the handoff document:

    tier 0  explain            — analysis only
    tier 1  scenario_analysis  — what-if analysis
    tier 2  recommendation     — produce a recommendation
    tier 3  stage              — stage a transaction   (approval required)
    tier 4  execute            — execute a transaction (approval required)

Advisory tiers (0–2) are auto-allowed. State-changing tiers (3–4) are gated:
the optimization math still runs, but the *action* it implies is withheld until
an authorized human approves it. :class:`ApprovalRecord` is the immutable
record of that governance decision, attached to every
:class:`OptimizationResult` produced under a governance controller.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ApprovalStatus(str, Enum):
    NOT_REQUIRED = "not_required"  # advisory tier — no approval needed
    PENDING = "pending"            # gated tier, awaiting a decision
    APPROVED = "approved"          # gated tier, approved — action performed
    REJECTED = "rejected"          # gated tier, rejected — action withheld


class ApprovalRecord(BaseModel):
    request_id: str
    execution_mode: str
    tier: int
    action: str                     # human-readable action the mode authorizes
    required: bool                  # whether human approval is required
    status: ApprovalStatus
    action_performed: bool          # whether the gated action was carried out
    approval_id: str | None = None  # stable id to reference a pending approval
    approver: str | None = None
    reason: str = ""
    decided_at: datetime | None = None

    model_config = {"frozen": True}
