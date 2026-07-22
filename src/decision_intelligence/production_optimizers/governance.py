"""Model-risk and config-promotion controls for production optimizers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from decision_intelligence.contracts import OptimizationRequest

from .contracts import ModelConfigSpec

PromotionStatus = Literal["approved", "pending", "rejected", "retired"]


class ModelRiskApprovalRecord(BaseModel):
    """Approval state for one optimizer model/config version."""

    optimizer_id: str
    model_name: str
    model_version: str
    config_version: str
    status: PromotionStatus
    approved_for: list[str] = Field(default_factory=list)
    approved_by: str | None = None
    approved_at: datetime | None = None
    change_ticket: str | None = None
    notes: str = ""

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.optimizer_id, self.model_version, self.config_version)


class ModelGovernanceDecision(BaseModel):
    """Decision returned by model/config promotion checks."""

    passed: bool
    record: ModelRiskApprovalRecord
    requested_mode: str
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProductionModelGovernanceRegistry:
    """In-memory registry of approved production model/config versions."""

    def __init__(self, records: list[ModelRiskApprovalRecord] | None = None) -> None:
        self._records: dict[tuple[str, str, str], ModelRiskApprovalRecord] = {}
        for record in records or []:
            self.register(record)

    def register(self, record: ModelRiskApprovalRecord) -> None:
        self._records[record.key] = record

    def evaluate(
        self,
        request: OptimizationRequest,
        model_config: ModelConfigSpec,
    ) -> ModelGovernanceDecision:
        record = self.get_or_default(model_config)
        requested_mode = str(request.execution_mode.value)
        blocking_issues: list[str] = []
        warnings: list[str] = []

        if record.status != "approved":
            blocking_issues.append(
                f"{model_config.optimizer_id} config {model_config.lineage.config_version} "
                f"is {record.status}, not approved."
            )
        if requested_mode not in record.approved_for:
            blocking_issues.append(
                f"{model_config.optimizer_id} config {model_config.lineage.config_version} "
                f"is not approved for execution mode '{requested_mode}'."
            )
        if model_config.lineage.change_ticket and not record.change_ticket:
            warnings.append(
                f"{model_config.optimizer_id} declares change ticket "
                f"{model_config.lineage.change_ticket}, but no promotion ticket is recorded."
            )

        return ModelGovernanceDecision(
            passed=not blocking_issues,
            record=record,
            requested_mode=requested_mode,
            blocking_issues=blocking_issues,
            warnings=warnings,
        )

    def get_or_default(self, model_config: ModelConfigSpec) -> ModelRiskApprovalRecord:
        key = (
            model_config.optimizer_id,
            model_config.lineage.model_version,
            model_config.lineage.config_version,
        )
        if key in self._records:
            return self._records[key]
        return approval_record_from_model_config(model_config)

    def list_records(self) -> list[ModelRiskApprovalRecord]:
        return [self._records[key] for key in sorted(self._records)]


def approval_record_from_model_config(
    model_config: ModelConfigSpec,
    *,
    approved_by: str = "model-risk-demo",
) -> ModelRiskApprovalRecord:
    """Create a default approved POC promotion record from model lineage."""

    return ModelRiskApprovalRecord(
        optimizer_id=model_config.optimizer_id,
        model_name=model_config.lineage.model_name,
        model_version=model_config.lineage.model_version,
        config_version=model_config.lineage.config_version,
        status="approved",
        approved_for=list(model_config.lineage.approved_for),
        approved_by=approved_by,
        approved_at=datetime.now(tz=UTC),
        change_ticket=model_config.lineage.change_ticket,
        notes="POC promotion record generated from ModelLineageSpec.",
    )


DEFAULT_MODEL_GOVERNANCE_REGISTRY = ProductionModelGovernanceRegistry()


def evaluate_model_governance(
    request: OptimizationRequest,
    model_config: ModelConfigSpec,
    registry: ProductionModelGovernanceRegistry | None = None,
) -> ModelGovernanceDecision:
    """Evaluate model/config approval for the requested execution mode."""

    active_registry = registry or DEFAULT_MODEL_GOVERNANCE_REGISTRY
    return active_registry.evaluate(request, model_config)
