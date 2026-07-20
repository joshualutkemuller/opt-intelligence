"""Typed source contracts for production optimizer data inputs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DataSourceContract(BaseModel):
    """Declared source expectation for one optimizer dataset."""

    dataset: str
    source_type: Literal["csv", "json", "document", "simulated", "service"]
    uri: str | None = None
    required: bool = True
    required_columns: list[str] = Field(default_factory=list)
    primary_keys: list[str] = Field(default_factory=list)
    owner: str = ""
    freshness_sla_hours: float | None = None
    snapshot_required: bool = True
    quality_checks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataSourceReport(BaseModel):
    """Observed quality, freshness, and lineage for one loaded source."""

    dataset: str
    source_type: str
    uri: str | None = None
    present: bool
    row_count: int = 0
    columns: list[str] = Field(default_factory=list)
    required_columns: list[str] = Field(default_factory=list)
    missing_columns: list[str] = Field(default_factory=list)
    primary_keys: list[str] = Field(default_factory=list)
    duplicate_key_count: int = 0
    content_hash: str | None = None
    last_modified_at: str | None = None
    observed_at: str
    stale: bool = False
    warnings: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataPreflightResult(BaseModel):
    """Aggregate data-source preflight result for a production optimizer request."""

    passed: bool
    snapshot_id: str
    reports: list[DataSourceReport] = Field(default_factory=list)
    checked_datasets: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
