"""Registry for production optimizer adapters."""

from __future__ import annotations

from .adapter import ProductionOptimizerAdapter
from .adapters import AssetAllocationMVOProductionAdapter, CollateralProductionAdapter


class ProductionOptimizerRegistry:
    """Single source of truth for production optimizer adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, ProductionOptimizerAdapter] = {}

    def register(self, adapter: ProductionOptimizerAdapter) -> None:
        if adapter.optimizer_id in self._adapters:
            raise ValueError(f"Production optimizer already registered: {adapter.optimizer_id}")
        self._adapters[adapter.optimizer_id] = adapter

    def get(self, optimizer_id: str) -> ProductionOptimizerAdapter:
        try:
            return self._adapters[optimizer_id]
        except KeyError as exc:
            available = ", ".join(self.list_ids()) or "none"
            raise KeyError(
                f"Unknown production optimizer '{optimizer_id}'. Available: {available}"
            ) from exc

    def list_ids(self) -> list[str]:
        return sorted(self._adapters)

    def __contains__(self, optimizer_id: str) -> bool:
        return optimizer_id in self._adapters


def build_default_production_registry() -> ProductionOptimizerRegistry:
    """Create a registry with production adapters currently implemented."""

    registry = ProductionOptimizerRegistry()
    registry.register(AssetAllocationMVOProductionAdapter())
    registry.register(CollateralProductionAdapter())
    return registry
