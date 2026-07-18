"""Execution-isolation scaffolding for production optimizer adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .contracts import ExecutionIsolationSpec


class OptimizerExecutionBackend(ABC):
    """Boundary for in-process, subprocess, service, batch, or container runs."""

    @abstractmethod
    def execute(
        self,
        spec: ExecutionIsolationSpec,
        problem: dict[str, Any],
    ) -> dict[str, Any]:
        """Run the native optimizer and return a native solution payload."""


class InProcessExecutionBackend(OptimizerExecutionBackend):
    """Minimal backend for Python-callable optimizers during initial migration."""

    def execute(
        self,
        spec: ExecutionIsolationSpec,
        problem: dict[str, Any],
    ) -> dict[str, Any]:
        callable_ref = problem.get("callable")
        if not callable(callable_ref):
            raise ValueError("In-process execution requires problem['callable'].")
        return callable_ref(problem)
