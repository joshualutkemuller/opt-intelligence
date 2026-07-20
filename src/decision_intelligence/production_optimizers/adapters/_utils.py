"""Shared helpers for production optimizer adapter implementations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

import numpy as np

from decision_intelligence.contracts.results import SolveStatus

from ..contracts import ModelConfigSpec


def data_snapshot_id(domain: str, portfolio_id: str, context: dict[str, Any]) -> str:
    """Return a stable data snapshot label for simulated or explicit data sources."""

    explicit = context.get("data_snapshot_id")
    if explicit:
        return str(explicit)
    source = context.get("data_source", {"type": "simulated"})
    source_type = source.get("type", "simulated") if isinstance(source, dict) else "unknown"
    seed = context.get("seed", 42)
    return f"{domain}:{portfolio_id}:{source_type}:seed={seed}"


def reproducibility_fingerprint(
    *,
    model_config: ModelConfigSpec,
    request_payload: dict[str, Any],
    snapshot_id: str | None,
) -> str:
    """Hash model config, request payload, and data snapshot into a run fingerprint."""

    payload = {
        "model_config": model_config.model_dump(mode="json"),
        "request": request_payload,
        "data_snapshot_id": snapshot_id,
    }
    raw = json.dumps(to_jsonable(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_status(status: Any) -> str:
    """Map native optimizer status values to production normalized statuses."""

    raw = status.value if isinstance(status, Enum) else str(status)
    if raw == SolveStatus.OPTIMAL.value:
        return "optimal"
    if raw == SolveStatus.INFEASIBLE.value:
        return "infeasible"
    if raw == SolveStatus.UNBOUNDED.value:
        return "infeasible"
    return "error"


def to_jsonable(value: Any) -> Any:
    """Convert dataclasses, enums, numpy values, and nested payloads to JSON-like data."""

    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [to_jsonable(v) for v in value]
    return value


def allocation_dicts(allocations: list[Any]) -> list[dict[str, Any]]:
    """Normalize existing AllocationItem or dict allocation rows."""

    rows: list[dict[str, Any]] = []
    for allocation in allocations:
        if hasattr(allocation, "model_dump"):
            rows.append(allocation.model_dump(mode="json"))
        else:
            rows.append(to_jsonable(allocation))
    return rows
