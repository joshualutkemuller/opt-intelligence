"""Local production data adapters used by optimizer preflight checks."""

from __future__ import annotations

import csv
import hashlib
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path

from .contracts import DataSourceContract, DataSourceReport


class ProductionDataAdapter(ABC):
    """Base interface for production data-source adapters."""

    source_type: str

    @abstractmethod
    def inspect(self, contract: DataSourceContract) -> DataSourceReport:
        """Inspect source availability, shape, freshness, and snapshot lineage."""


class LocalCsvDataAdapter(ProductionDataAdapter):
    """Inspect a local CSV file without mutating optimizer payloads."""

    source_type = "csv"

    def inspect(self, contract: DataSourceContract) -> DataSourceReport:
        path = _path(contract)
        observed_at = _now_iso()
        if path is None or not path.exists():
            return _missing_report(contract, observed_at)

        columns: list[str] = []
        row_count = 0
        duplicate_key_count = 0
        warnings: list[str] = []
        blocking_issues: list[str] = []

        has_header = bool(contract.metadata.get("has_header", True))
        if has_header:
            with path.open(newline="") as handle:
                reader = csv.DictReader(handle)
                columns = list(reader.fieldnames or [])
                key_values: set[tuple[str, ...]] = set()
                for row in reader:
                    row_count += 1
                    key = tuple(str(row.get(item, "")) for item in contract.primary_keys)
                    if contract.primary_keys and key in key_values:
                        duplicate_key_count += 1
                    key_values.add(key)
        else:
            with path.open(newline="") as handle:
                row_count = sum(1 for row in csv.reader(handle) if row)

        missing_columns = [item for item in contract.required_columns if item not in columns]
        if missing_columns:
            blocking_issues.append(
                f"{contract.dataset} missing required columns: {missing_columns}"
            )
        if duplicate_key_count:
            blocking_issues.append(
                f"{contract.dataset} has {duplicate_key_count} duplicate primary keys."
            )
        if row_count == 0:
            blocking_issues.append(f"{contract.dataset} contained no data rows.")

        stale = _is_stale(path, contract)
        if stale:
            warnings.append(
                f"{contract.dataset} is older than freshness SLA "
                f"({contract.freshness_sla_hours}h)."
            )

        return DataSourceReport(
            dataset=contract.dataset,
            source_type=self.source_type,
            uri=str(path),
            present=True,
            row_count=row_count,
            columns=columns,
            required_columns=contract.required_columns,
            missing_columns=missing_columns,
            primary_keys=contract.primary_keys,
            duplicate_key_count=duplicate_key_count,
            content_hash=_file_hash(path),
            last_modified_at=_mtime_iso(path),
            observed_at=observed_at,
            stale=stale,
            warnings=warnings,
            blocking_issues=blocking_issues,
            metadata=contract.metadata,
        )


class LocalJsonDataAdapter(ProductionDataAdapter):
    """Inspect a local JSON source used for policy or model data."""

    source_type = "json"

    def inspect(self, contract: DataSourceContract) -> DataSourceReport:
        path = _path(contract)
        observed_at = _now_iso()
        if path is None or not path.exists():
            return _missing_report(contract, observed_at)

        warnings: list[str] = []
        blocking_issues: list[str] = []
        columns: list[str] = []
        row_count = 0
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            blocking_issues.append(f"{contract.dataset} JSON parse failed: {exc}")
            payload = None

        if isinstance(payload, list):
            row_count = len(payload)
            if payload and isinstance(payload[0], dict):
                columns = sorted({str(key) for row in payload for key in row})
        elif isinstance(payload, dict):
            row_count = 1
            columns = sorted(str(key) for key in payload)
        elif payload is not None:
            row_count = 1

        missing_columns = [item for item in contract.required_columns if item not in columns]
        if missing_columns:
            blocking_issues.append(
                f"{contract.dataset} missing required fields: {missing_columns}"
            )
        stale = _is_stale(path, contract)
        if stale:
            warnings.append(
                f"{contract.dataset} is older than freshness SLA "
                f"({contract.freshness_sla_hours}h)."
            )

        return DataSourceReport(
            dataset=contract.dataset,
            source_type=self.source_type,
            uri=str(path),
            present=True,
            row_count=row_count,
            columns=columns,
            required_columns=contract.required_columns,
            missing_columns=missing_columns,
            primary_keys=contract.primary_keys,
            content_hash=_file_hash(path),
            last_modified_at=_mtime_iso(path),
            observed_at=observed_at,
            stale=stale,
            warnings=warnings,
            blocking_issues=blocking_issues,
            metadata=contract.metadata,
        )


class LocalDocumentDataAdapter(ProductionDataAdapter):
    """Inspect a local text/PDF policy document source for lineage evidence."""

    source_type = "document"

    def inspect(self, contract: DataSourceContract) -> DataSourceReport:
        path = _path(contract)
        observed_at = _now_iso()
        if path is None or not path.exists():
            return _missing_report(contract, observed_at)

        stale = _is_stale(path, contract)
        warnings = []
        if stale:
            warnings.append(
                f"{contract.dataset} is older than freshness SLA "
                f"({contract.freshness_sla_hours}h)."
            )
        return DataSourceReport(
            dataset=contract.dataset,
            source_type=self.source_type,
            uri=str(path),
            present=True,
            row_count=1,
            columns=[],
            required_columns=contract.required_columns,
            primary_keys=contract.primary_keys,
            content_hash=_file_hash(path),
            last_modified_at=_mtime_iso(path),
            observed_at=observed_at,
            stale=stale,
            warnings=warnings,
            metadata=contract.metadata,
        )


class SimulatedDataAdapter(ProductionDataAdapter):
    """Record lineage for deterministic simulated or context-provided data."""

    source_type = "simulated"

    def inspect(self, contract: DataSourceContract) -> DataSourceReport:
        return DataSourceReport(
            dataset=contract.dataset,
            source_type=self.source_type,
            uri=contract.uri,
            present=True,
            row_count=int(contract.metadata.get("row_count", 0)),
            columns=contract.required_columns,
            required_columns=contract.required_columns,
            primary_keys=contract.primary_keys,
            content_hash=None,
            observed_at=_now_iso(),
            metadata=contract.metadata,
        )


def adapter_for_source(source_type: str) -> ProductionDataAdapter:
    """Return the adapter for a configured source type."""

    if source_type == "csv":
        return LocalCsvDataAdapter()
    if source_type == "json":
        return LocalJsonDataAdapter()
    if source_type in {"document", "pdf", "text"}:
        return LocalDocumentDataAdapter()
    if source_type == "simulated":
        return SimulatedDataAdapter()
    if source_type == "service":
        return SimulatedDataAdapter()
    raise ValueError(f"Unsupported production data source type: {source_type}")


def _path(contract: DataSourceContract) -> Path | None:
    if not contract.uri:
        return None
    return Path(contract.uri).expanduser()


def _missing_report(contract: DataSourceContract, observed_at: str) -> DataSourceReport:
    issue = f"{contract.dataset} source is missing: {contract.uri or 'no uri configured'}"
    return DataSourceReport(
        dataset=contract.dataset,
        source_type=contract.source_type,
        uri=contract.uri,
        present=False,
        required_columns=contract.required_columns,
        primary_keys=contract.primary_keys,
        observed_at=observed_at,
        blocking_issues=[issue] if contract.required else [],
        warnings=[] if contract.required else [issue],
        metadata=contract.metadata,
    )


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _is_stale(path: Path, contract: DataSourceContract) -> bool:
    if contract.freshness_sla_hours is None:
        return False
    age_seconds = datetime.now(tz=UTC).timestamp() - path.stat().st_mtime
    return age_seconds > contract.freshness_sla_hours * 3600
