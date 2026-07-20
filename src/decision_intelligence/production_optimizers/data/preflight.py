"""Build production data-source preflight reports from optimizer configs."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from decision_intelligence.contracts import OptimizationRequest
from decision_intelligence.production_optimizers.contracts import ModelConfigSpec

from .adapters import adapter_for_source
from .contracts import DataPreflightResult, DataSourceContract, DataSourceReport

_LEGACY_DATA_SOURCE_MAP: dict[str, dict[str, str]] = {
    "asset_allocation": {
        "asset_universe": "assets",
        "covariance_matrix": "covariance",
    },
    "collateral": {
        "collateral_inventory": "assets",
        "margin_obligations": "obligations",
    },
    "financing": {
        "financing_counterparties": "counterparties",
        "funding_needs": "needs",
    },
    "money_market": {
        "money_market_fund_universe": "funds",
        "cash_position": "position",
    },
}


def build_data_preflight_report(
    request: OptimizationRequest,
    model_config: ModelConfigSpec,
) -> DataPreflightResult:
    """Inspect configured production data sources for one optimizer request."""

    contracts = _source_contracts(request, model_config)
    reports: list[DataSourceReport] = []
    for contract in contracts:
        try:
            report = adapter_for_source(contract.source_type).inspect(contract)
        except Exception as exc:  # noqa: BLE001 - preflight should fail closed.
            report = DataSourceReport(
                dataset=contract.dataset,
                source_type=contract.source_type,
                uri=contract.uri,
                present=False,
                required_columns=contract.required_columns,
                primary_keys=contract.primary_keys,
                observed_at="",
                blocking_issues=[f"{contract.dataset} source inspection failed: {exc}"],
                metadata=contract.metadata,
            )
        reports.append(report)

    warnings = [warning for report in reports for warning in report.warnings]
    blocking_issues = [issue for report in reports for issue in report.blocking_issues]
    checked_datasets = {report.dataset: report.row_count for report in reports}
    snapshot_id = _snapshot_id(request, model_config, reports)
    return DataPreflightResult(
        passed=not blocking_issues,
        snapshot_id=snapshot_id,
        reports=reports,
        checked_datasets=checked_datasets,
        warnings=warnings,
        blocking_issues=blocking_issues,
    )


def _source_contracts(
    request: OptimizationRequest,
    model_config: ModelConfigSpec,
) -> list[DataSourceContract]:
    configured = request.context.get("production_data_sources")
    if isinstance(configured, dict) and configured:
        return _configured_source_contracts(configured, model_config)

    legacy = request.context.get("data_source")
    if isinstance(legacy, dict) and legacy.get("type") == "csv":
        return _legacy_csv_contracts(legacy, model_config)

    return _simulated_source_contracts(request, model_config)


def _configured_source_contracts(
    configured: dict[str, Any],
    model_config: ModelConfigSpec,
) -> list[DataSourceContract]:
    contracts: list[DataSourceContract] = []
    required = set(model_config.data_contract.required_datasets)
    optional = set(model_config.data_contract.optional_datasets)
    for dataset in [*required, *optional]:
        payload = configured.get(dataset)
        if not isinstance(payload, dict):
            if dataset in required:
                contracts.append(_missing_config_contract(dataset, model_config))
            continue
        source_type = str(payload.get("type", "csv"))
        contracts.append(
            DataSourceContract(
                dataset=dataset,
                source_type=_normalized_source_type(source_type),
                uri=payload.get("uri") or payload.get("path"),
                required=bool(payload.get("required", dataset in required)),
                required_columns=list(
                    payload.get(
                        "required_columns",
                        model_config.data_contract.required_columns.get(dataset, []),
                    )
                ),
                primary_keys=list(
                    payload.get(
                        "primary_keys",
                        model_config.data_contract.primary_keys.get(dataset, []),
                    )
                ),
                owner=str(payload.get("owner", "")),
                freshness_sla_hours=_optional_float(payload.get("freshness_sla_hours")),
                snapshot_required=bool(
                    payload.get("snapshot_required", model_config.data_contract.snapshot_required)
                ),
                metadata={
                    key: value
                    for key, value in payload.items()
                    if key
                    not in {
                        "type",
                        "uri",
                        "path",
                        "required",
                        "required_columns",
                        "primary_keys",
                        "owner",
                        "freshness_sla_hours",
                        "snapshot_required",
                    }
                },
            )
        )
    return contracts


def _legacy_csv_contracts(
    legacy: dict[str, Any],
    model_config: ModelConfigSpec,
) -> list[DataSourceContract]:
    dataset_map = _LEGACY_DATA_SOURCE_MAP.get(model_config.domain, {})
    contracts: list[DataSourceContract] = []
    for dataset in model_config.data_contract.required_datasets:
        source_key = dataset_map.get(dataset, dataset)
        uri = legacy.get(source_key)
        metadata: dict[str, Any] = {"legacy_data_source_key": source_key}
        required_columns = _legacy_required_columns(model_config.domain, dataset, model_config)
        if dataset == "covariance_matrix":
            metadata["has_header"] = False
            required_columns = []
        contracts.append(
            DataSourceContract(
                dataset=dataset,
                source_type="csv" if uri else "simulated",
                uri=uri,
                required=bool(uri),
                required_columns=list(required_columns),
                primary_keys=list(model_config.data_contract.primary_keys.get(dataset, [])),
                snapshot_required=model_config.data_contract.snapshot_required,
                metadata=metadata,
            )
        )
    return contracts


def _simulated_source_contracts(
    request: OptimizationRequest,
    model_config: ModelConfigSpec,
) -> list[DataSourceContract]:
    _ = request
    return [
        DataSourceContract(
            dataset=dataset,
            source_type="simulated",
            uri=f"simulated://{model_config.domain}/{dataset}",
            required=True,
            required_columns=list(model_config.data_contract.required_columns.get(dataset, [])),
            primary_keys=list(model_config.data_contract.primary_keys.get(dataset, [])),
            snapshot_required=model_config.data_contract.snapshot_required,
            metadata={
                "source_note": "deterministic simulated or context-provided demo data",
            },
        )
        for dataset in model_config.data_contract.required_datasets
    ]


def _legacy_required_columns(
    domain: str,
    dataset: str,
    model_config: ModelConfigSpec,
) -> list[str]:
    columns = list(model_config.data_contract.required_columns.get(dataset, []))
    if domain == "collateral" and dataset == "margin_obligations":
        return [
            item
            for item in columns
            if item not in {"venue_type", "agreement_type"}
        ]
    if domain == "asset_allocation" and dataset == "covariance_matrix":
        return []
    return columns


def _missing_config_contract(
    dataset: str,
    model_config: ModelConfigSpec,
) -> DataSourceContract:
    return DataSourceContract(
        dataset=dataset,
        source_type="csv",
        uri=None,
        required=True,
        required_columns=list(model_config.data_contract.required_columns.get(dataset, [])),
        primary_keys=list(model_config.data_contract.primary_keys.get(dataset, [])),
        snapshot_required=model_config.data_contract.snapshot_required,
        metadata={"source_note": "missing production_data_sources entry"},
    )


def _normalized_source_type(source_type: str) -> str:
    if source_type == "pdf":
        return "document"
    if source_type == "text":
        return "document"
    return source_type


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _snapshot_id(
    request: OptimizationRequest,
    model_config: ModelConfigSpec,
    reports: list[DataSourceReport],
) -> str:
    payload = {
        "optimizer_id": model_config.optimizer_id,
        "portfolio_id": request.portfolio_id,
        "reports": [
            {
                "dataset": report.dataset,
                "uri": report.uri,
                "content_hash": report.content_hash,
                "row_count": report.row_count,
            }
            for report in reports
        ],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    return f"DATA-{model_config.domain.upper()}-{digest}"
