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
from .registry import ProductionOptimizerRegistry

__all__ = [
    "ConstraintFamilySpec",
    "DataContractSpec",
    "ExecutionIsolationSpec",
    "LimitSourceSpec",
    "ModelConfigSpec",
    "ModelLineageSpec",
    "NormalizedOptimizerResult",
    "ObjectiveTermSpec",
    "PreflightReport",
    "ProductionOptimizerAdapter",
    "ProductionOptimizerEvidence",
    "ProductionOptimizerRegistry",
    "ScenarioKnobSpec",
    "SolverBackendSpec",
]
