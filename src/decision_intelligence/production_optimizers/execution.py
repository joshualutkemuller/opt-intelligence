"""Execution-isolation scaffolding for production optimizer adapters."""

from __future__ import annotations

import json
import subprocess
from abc import ABC, abstractmethod
from typing import Any
from urllib import request as urllib_request

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


class SubprocessExecutionBackend(OptimizerExecutionBackend):
    """Execute an optimizer command by exchanging structured JSON over stdio."""

    def execute(
        self,
        spec: ExecutionIsolationSpec,
        problem: dict[str, Any],
    ) -> dict[str, Any]:
        if not spec.command:
            raise ValueError("Subprocess execution requires spec.command.")

        payload = json.dumps(
            {"spec": spec.model_dump(mode="json"), "problem": _jsonable(problem)},
            sort_keys=True,
        )
        completed = subprocess.run(
            spec.command,
            input=payload,
            capture_output=True,
            check=False,
            encoding="utf-8",
            timeout=spec.timeout_seconds,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or "no stderr"
            raise RuntimeError(
                f"Subprocess optimizer failed with code {completed.returncode}: {stderr}"
            )
        stdout = completed.stdout.strip()
        if not stdout:
            raise RuntimeError("Subprocess optimizer returned no JSON payload.")
        return _loads_solution(stdout, source="subprocess stdout")


class RestExecutionBackend(OptimizerExecutionBackend):
    """Execute an optimizer through a JSON HTTP POST service boundary."""

    def execute(
        self,
        spec: ExecutionIsolationSpec,
        problem: dict[str, Any],
    ) -> dict[str, Any]:
        if not spec.endpoint:
            raise ValueError("REST execution requires spec.endpoint.")

        payload = json.dumps(
            {"spec": spec.model_dump(mode="json"), "problem": _jsonable(problem)},
            sort_keys=True,
        ).encode("utf-8")
        request = urllib_request.Request(
            spec.endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        attempts = max(1, spec.retry_count + 1)
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                with urllib_request.urlopen(request, timeout=spec.timeout_seconds) as response:
                    status = int(getattr(response, "status", 200))
                    body = response.read().decode("utf-8")
                if status >= 400:
                    raise RuntimeError(f"REST optimizer returned HTTP {status}: {body}")
                return _loads_solution(body, source="REST response")
            except Exception as exc:  # noqa: BLE001 - retry boundary must preserve final error.
                last_error = exc
        raise RuntimeError(f"REST optimizer execution failed: {last_error}") from last_error


class UnsupportedExecutionBackend(OptimizerExecutionBackend):
    """Explicit placeholder for modes that require firm infrastructure."""

    def execute(
        self,
        spec: ExecutionIsolationSpec,
        problem: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError(
            f"Execution mode '{spec.mode}' requires a firm-specific backend adapter."
        )


def backend_for_spec(spec: ExecutionIsolationSpec) -> OptimizerExecutionBackend:
    """Return the concrete execution backend for a production optimizer spec."""

    if spec.mode == "in_process":
        return InProcessExecutionBackend()
    if spec.mode == "subprocess":
        return SubprocessExecutionBackend()
    if spec.mode == "rest":
        return RestExecutionBackend()
    return UnsupportedExecutionBackend()


def execute_isolated(
    spec: ExecutionIsolationSpec,
    problem: dict[str, Any],
) -> dict[str, Any]:
    """Convenience wrapper used by adapters that delegate to isolation specs."""

    return backend_for_spec(spec).execute(spec, problem)


def _loads_solution(raw: str, *, source: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not decode optimizer JSON from {source}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Optimizer JSON from {source} must be an object.")
    return payload


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_jsonable(item) for item in value]
    return value
