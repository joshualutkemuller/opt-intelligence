"""Production data adapter layer for optimizer source contracts."""

from .adapters import (
    LocalCsvDataAdapter,
    LocalDocumentDataAdapter,
    LocalJsonDataAdapter,
    ProductionDataAdapter,
    adapter_for_source,
)
from .contracts import (
    DataPreflightResult,
    DataSourceContract,
    DataSourceReport,
)
from .preflight import build_data_preflight_report

__all__ = [
    "DataPreflightResult",
    "DataSourceContract",
    "DataSourceReport",
    "LocalCsvDataAdapter",
    "LocalDocumentDataAdapter",
    "LocalJsonDataAdapter",
    "ProductionDataAdapter",
    "adapter_for_source",
    "build_data_preflight_report",
]
