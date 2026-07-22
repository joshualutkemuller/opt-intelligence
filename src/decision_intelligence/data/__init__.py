# Data layer — resolves each optimizer's dataset from a configurable source
# (simulated by default, or real data via CSV). See loaders.py.

from .loaders import (
    DataSourceError,
    load_asset_allocation,
    load_collateral,
    load_dataclass_csv,
    load_financing,
    load_money_market,
)
from .quality import (
    DataQualityReport,
    DataQualityResult,
    DataQualityViolation,
    run_quality_checks,
)

__all__ = [
    "DataSourceError",
    "load_asset_allocation",
    "load_collateral",
    "load_financing",
    "load_money_market",
    "load_dataclass_csv",
    "DataQualityReport",
    "DataQualityResult",
    "DataQualityViolation",
    "run_quality_checks",
]
