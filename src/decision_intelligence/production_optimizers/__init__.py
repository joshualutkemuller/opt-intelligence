"""Production optimizer adapter framework scaffold.

This package is the intentionally obvious home for future firm-developed
optimizer integrations. It does not replace the current POC optimizers; it
defines the production-grade contracts those optimizers can migrate toward.
"""

from .adapter import ProductionOptimizerAdapter
from .contracts import (
    ConstraintFamilySpec,
    DataContractSpec,
    ExecutionIsolationSpec,
    LimitSourceSpec,
    ModelConfigSpec,
    ModelLineageSpec,
    NormalizedOptimizerResult,
    ObjectiveTermSpec,
    PreflightReport,
    ProductionOptimizerEvidence,
    ScenarioKnobSpec,
    SolverBackendSpec,
)
from .data import (
    DataPreflightResult,
    DataSourceContract,
    DataSourceReport,
    build_data_preflight_report,
)
from .evidence import EvidenceManifest, LocalProductionEvidenceStore
from .execution import (
    InProcessExecutionBackend,
    OptimizerExecutionBackend,
    RestExecutionBackend,
    SubprocessExecutionBackend,
    backend_for_spec,
    execute_isolated,
)
from .governance import (
    ModelGovernanceDecision,
    ModelRiskApprovalRecord,
    ProductionModelGovernanceRegistry,
    evaluate_model_governance,
)
from .registry import ProductionOptimizerRegistry, build_default_production_registry

__all__ = [
    "AssetAllocationMVOProductionAdapter",
    "CashMovementProductionAdapter",
    "CollateralProductionAdapter",
    "ConstraintFamilySpec",
    "DataContractSpec",
    "DataPreflightResult",
    "DataSourceContract",
    "DataSourceReport",
    "EvidenceManifest",
    "ExecutionIsolationSpec",
    "InProcessExecutionBackend",
    "FinancingProductionAdapter",
    "LimitSourceSpec",
    "LocalProductionEvidenceStore",
    "ModelConfigSpec",
    "ModelGovernanceDecision",
    "ModelLineageSpec",
    "ModelRiskApprovalRecord",
    "MarginCallWorkflowProductionAdapter",
    "MoneyMarketProductionAdapter",
    "NormalizedOptimizerResult",
    "ObjectiveTermSpec",
    "OptimizerExecutionBackend",
    "PreflightReport",
    "ProductionOptimizerAdapter",
    "ProductionOptimizerEvidence",
    "ProductionModelGovernanceRegistry",
    "ProductionOptimizerRegistry",
    "RestExecutionBackend",
    "ScenarioKnobSpec",
    "SolverBackendSpec",
    "SubprocessExecutionBackend",
    "backend_for_spec",
    "build_default_production_registry",
    "build_data_preflight_report",
    "evaluate_model_governance",
    "execute_isolated",
]


def __getattr__(name: str):
    if name == "AssetAllocationMVOProductionAdapter":
        from .adapters import AssetAllocationMVOProductionAdapter

        return AssetAllocationMVOProductionAdapter
    if name == "CollateralProductionAdapter":
        from .adapters import CollateralProductionAdapter

        return CollateralProductionAdapter
    if name == "FinancingProductionAdapter":
        from .adapters import FinancingProductionAdapter

        return FinancingProductionAdapter
    if name == "CashMovementProductionAdapter":
        from .adapters import CashMovementProductionAdapter

        return CashMovementProductionAdapter
    if name == "MarginCallWorkflowProductionAdapter":
        from .adapters import MarginCallWorkflowProductionAdapter

        return MarginCallWorkflowProductionAdapter
    if name == "MoneyMarketProductionAdapter":
        from .adapters import MoneyMarketProductionAdapter

        return MoneyMarketProductionAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
