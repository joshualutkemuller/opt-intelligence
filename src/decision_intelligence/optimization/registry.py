"""Optimizer registry — single source of truth for registered capabilities."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class OptimizerRegistry:
    def __init__(self) -> None:
        self._optimizers: dict[str, Any] = {}

    def register(self, optimizer: Any) -> None:
        name = optimizer.domain
        if name in self._optimizers:
            raise ValueError(f"Optimizer already registered for domain: {name}")
        self._optimizers[name] = optimizer
        logger.info("Registered optimizer: %s v%s", name, getattr(optimizer, "version", "?"))

    def get(self, domain: str) -> Any:
        if domain not in self._optimizers:
            raise KeyError(
                f"No optimizer registered for domain '{domain}'. "
                f"Available: {self.list_domains()}"
            )
        return self._optimizers[domain]

    def list_domains(self) -> list[str]:
        return sorted(self._optimizers)

    def __contains__(self, domain: str) -> bool:
        return domain in self._optimizers

    def __len__(self) -> int:
        return len(self._optimizers)
