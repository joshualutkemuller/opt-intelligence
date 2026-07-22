"""
Data provider layer — resolves each optimizer's input dataset from a
configurable source without changing the LP formulation.

Every optimizer's ``prepare_problem`` asks this module for its domain dataset
(e.g. ``load_money_market(request)``) instead of calling ``simulate_*`` directly.
The source is selected by ``request.context["data_source"]``:

    # default — reproducible simulated data (backward compatible)
    context = {"seed": 42, "n_funds": 8}

    # real data from CSV files
    context = {
        "data_source": {
            "type": "csv",
            "funds": "data/mmf_universe.csv",
            "position": "data/cash_position.csv",   # optional, single row
        }
    }

Each loader returns exactly the same dataclass tuple the simulator returns, so
adding a real feed is a config change, not a code change in the optimizer.

CSV columns map 1:1 to dataclass field names; types are coerced from the
dataclass annotations. List-valued fields (e.g. ``eligible_asset_classes``) are
written as ``;``-separated strings.
"""

from __future__ import annotations

import csv
import typing
from dataclasses import MISSING, fields, is_dataclass
from pathlib import Path
from typing import Any, TypeVar

from decision_intelligence.contracts import OptimizationRequest
from decision_intelligence.optimizers.asset_allocation.data import (
    AssetClassAssumption,
    simulate_asset_universe,
)
from decision_intelligence.optimizers.collateral.data import (
    CollateralAsset,
    CollateralObligation,
    simulate_inventory,
)
from decision_intelligence.optimizers.financing.data import (
    FinancingCounterparty,
    FundingNeed,
    simulate_financing_universe,
)
from decision_intelligence.optimizers.money_market.data import (
    CashPosition,
    MoneyMarketFund,
    simulate_universe,
)

T = TypeVar("T")

_TRUE = {"1", "true", "yes", "y", "t"}
_LIST_SEP = ";"


class DataSourceError(ValueError):
    """Raised when a configured data source is missing or malformed."""


# --------------------------------------------------------------------------- #
# Generic CSV → dataclass coercion
# --------------------------------------------------------------------------- #
def _coerce_scalar(value: str, annotation: Any) -> Any:
    origin = typing.get_origin(annotation)

    # Optional[X] / X | None → unwrap to the first non-None arg.
    if origin is typing.Union or (origin is not None and str(origin) == "types.UnionType"):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        annotation = args[0] if args else str
        origin = typing.get_origin(annotation)

    if origin in (list, typing.List):  # noqa: UP006
        (inner,) = typing.get_args(annotation) or (str,)
        raw = value.strip()
        if not raw:
            return []
        return [_coerce_scalar(part.strip(), inner) for part in raw.split(_LIST_SEP)]

    if annotation is bool:
        return value.strip().lower() in _TRUE
    if annotation is int:
        return int(float(value))  # tolerate "5.0"
    if annotation is float:
        return float(value)
    return value


def load_dataclass_csv(path: str | Path, dc_type: type[T]) -> list[T]:
    """Read a CSV whose columns are field names of ``dc_type`` into instances."""
    if not is_dataclass(dc_type):
        raise TypeError(f"{dc_type!r} is not a dataclass")

    p = Path(path)
    if not p.exists():
        raise DataSourceError(f"CSV not found: {p}")

    # Resolve real types — dataclasses using `from __future__ import annotations`
    # expose field.type as a string, so get_type_hints is required.
    annotations = typing.get_type_hints(dc_type)
    required = {
        f.name
        for f in fields(dc_type)
        if f.default is MISSING and f.default_factory is MISSING  # type: ignore[misc]
    }

    rows: list[T] = []
    with p.open(newline="") as fh:
        reader = csv.DictReader(fh)
        header = set(reader.fieldnames or [])
        missing = required - header
        if missing:
            raise DataSourceError(
                f"{p.name} is missing required columns for {dc_type.__name__}: "
                f"{sorted(missing)}"
            )
        for i, raw_row in enumerate(reader, start=2):  # header is line 1
            kwargs: dict[str, Any] = {}
            for name, ann in annotations.items():
                if name in raw_row and raw_row[name] not in (None, ""):
                    try:
                        kwargs[name] = _coerce_scalar(raw_row[name], ann)
                    except (ValueError, TypeError) as exc:
                        raise DataSourceError(
                            f"{p.name} line {i}: bad value for '{name}': "
                            f"{raw_row[name]!r} ({exc})"
                        ) from exc
            rows.append(dc_type(**kwargs))
    if not rows:
        raise DataSourceError(f"{p.name} contained no data rows")
    return rows


# --------------------------------------------------------------------------- #
# Source resolution
# --------------------------------------------------------------------------- #
def _source(request: OptimizationRequest) -> dict[str, Any]:
    src = request.context.get("data_source") or {"type": "simulated"}
    if not isinstance(src, dict) or "type" not in src:
        raise DataSourceError(
            "context['data_source'] must be a dict with a 'type' key "
            "('simulated' or 'csv')."
        )
    return src


def _require(src: dict[str, Any], key: str, domain: str) -> str:
    if key not in src:
        raise DataSourceError(
            f"csv data_source for '{domain}' requires a '{key}' path."
        )
    return src[key]


# --------------------------------------------------------------------------- #
# Per-domain loaders — each mirrors the corresponding simulate_* return shape
# --------------------------------------------------------------------------- #
def load_collateral(
    request: OptimizationRequest,
) -> tuple[list[CollateralAsset], list[CollateralObligation]]:
    src = _source(request)
    if src["type"] == "simulated":
        return simulate_inventory(
            n_assets=request.context.get("n_assets", 20),
            seed=request.context.get("seed", 42),
            context_overrides=request.context,
        )
    if src["type"] == "csv":
        assets = load_dataclass_csv(_require(src, "assets", "collateral"), CollateralAsset)
        obligations = load_dataclass_csv(
            _require(src, "obligations", "collateral"), CollateralObligation
        )
        return assets, obligations
    if src["type"] == "collateral_db":
        return _load_collateral_from_db(request, src)
    raise DataSourceError(f"Unknown data_source type '{src['type']}' for collateral.")


# Canonical CollateralDB asset class → optimizer asset_class string
_COLLATERAL_DB_CLASS_MAP: dict[str, str] = {
    "CASH": "cash",
    "GOVT": "govt_bond",
    "AGENCY": "govt_bond",
    "CORP": "corp_bond",
    "HY_CORP": "corp_bond",
    "EQUITY": "equity",
    "ABS": "corp_bond",
    "MBS": "corp_bond",
    "MUNI": "govt_bond",
    "MMF": "cash",
    "COVERED": "corp_bond",
    "OTHER": "corp_bond",
}


def _map_db_asset_class(db_class: str) -> str:
    return _COLLATERAL_DB_CLASS_MAP.get(db_class.upper(), "corp_bond")


def _load_collateral_from_db(
    request: OptimizationRequest,
    src: dict[str, Any],
) -> tuple[list[CollateralAsset], list[CollateralObligation]]:
    """Load eligibility rules from CollateralDatabase; overlay on simulated inventory.

    Required context keys
    ---------------------
    ``data_source.agreement_id`` or ``context.agreement_id``
        The margin agreement whose schedule drives eligibility and haircuts.

    Optional context keys
    ---------------------
    ``data_source.db_path``
        Path to the SQLite file (defaults to ``CollateralDatabase`` default path).
    ``context.required_value``
        Post-haircut USD amount the obligation must cover.  Falls back to the
        agreement's ``mta_amount`` and then $10 M.
    ``data_source.inventory``
        Path to a CSV of real inventory positions (columns = ``CollateralAsset``
        field names).  When present the simulation is skipped entirely and the
        eligibility/haircut rules from the DB are applied on top of real holdings.
    ``context.n_assets``, ``context.seed``
        Forwarded to ``simulate_inventory`` when no *inventory* path is given.
    """
    try:
        from collateral_schedule import CollateralDatabase
    except ImportError as exc:
        raise DataSourceError(
            "collateral_db source requires the 'collateral_schedule' package."
        ) from exc

    agreement_id = src.get("agreement_id") or request.context.get("agreement_id")
    if not agreement_id:
        raise DataSourceError(
            "collateral_db source requires 'agreement_id' in data_source or context."
        )

    db_path = src.get("db_path")
    db = CollateralDatabase(db_path) if db_path else CollateralDatabase()

    agr = db.get_agreement(agreement_id)
    if agr is None:
        raise DataSourceError(
            f"Agreement '{agreement_id}' not found in CollateralDatabase."
        )

    entries = db.list_entries(agreement_id)

    # Derive eligibility and haircut/concentration rules from the schedule entries.
    # When multiple rows exist for the same optimizer asset class (e.g. GOVT + AGENCY
    # both map to govt_bond) we use the minimum haircut (most favourable rule) and
    # the minimum concentration limit (most restrictive rule).
    eligible_classes: set[str] = set()
    haircut_by_class: dict[str, float] = {}
    conc_by_class: dict[str, float] = {}

    for entry in entries:
        ac = _map_db_asset_class(entry["asset_class"])
        if entry.get("eligible"):
            eligible_classes.add(ac)
        hc = entry.get("haircut_pct")
        if hc is not None:
            current = haircut_by_class.get(ac)
            if current is None or hc < current:
                haircut_by_class[ac] = hc / 100.0  # % → fraction
        conc = entry.get("concentration_limit_pct")
        if conc is not None:
            current = conc_by_class.get(ac)
            if current is None or conc < current:
                conc_by_class[ac] = conc / 100.0

    # Base inventory: real CSV positions feed if provided, else simulation.
    # The CSV must have columns matching CollateralAsset field names.
    inventory_path = src.get("inventory")
    if inventory_path:
        base_assets = load_dataclass_csv(inventory_path, CollateralAsset)
    else:
        base_assets, _ = simulate_inventory(
            n_assets=request.context.get("n_assets", 20),
            seed=request.context.get("seed", 42),
            context_overrides=request.context,
        )

    # Apply schedule rules: override eligible flag and haircut per asset class.
    for asset in base_assets:
        ac = asset.asset_class
        asset.eligible = ac in eligible_classes
        if ac in haircut_by_class:
            asset.haircut = haircut_by_class[ac]

    # Propagate the tightest concentration limit to request context so the
    # optimizer's concentration constraint picks it up automatically.
    if conc_by_class:
        tightest = min(conc_by_class.values())
        request.context.setdefault("concentration_limit", tightest)

    # Resolve the counterparty name for human-readable output.
    cp_map = {c["id"]: c["name"] for c in db.list_counterparties()}
    counterparty_name = cp_map.get(agr["counterparty_id"], agr["counterparty_id"])

    required_value = float(
        request.context.get("required_value")
        or agr.get("mta_amount")
        or 10_000_000.0
    )

    obligation = CollateralObligation(
        obligation_id=agreement_id,
        counterparty=counterparty_name,
        required_value=required_value,
        eligible_asset_classes=sorted(eligible_classes),
        venue_type="bilateral",
        agreement_type=agr.get("margin_type", "OTHER"),
    )

    return base_assets, [obligation]


def load_money_market(
    request: OptimizationRequest,
) -> tuple[list[MoneyMarketFund], CashPosition]:
    src = _source(request)
    if src["type"] == "simulated":
        return simulate_universe(
            n_funds=request.context.get("n_funds", 8),
            seed=request.context.get("seed", 42),
            context_overrides=request.context,
        )
    if src["type"] == "csv":
        funds = load_dataclass_csv(_require(src, "funds", "money_market"), MoneyMarketFund)
        position = _build_cash_position(request, src, funds)
        return funds, position
    raise DataSourceError(f"Unknown data_source type '{src['type']}' for money_market.")


def load_financing(
    request: OptimizationRequest,
) -> tuple[list[FinancingCounterparty], list[FundingNeed]]:
    src = _source(request)
    if src["type"] == "simulated":
        return simulate_financing_universe(
            n_counterparties=request.context.get("n_counterparties", 10),
            seed=request.context.get("seed", 42),
            context_overrides=request.context,
        )
    if src["type"] == "csv":
        counterparties = load_dataclass_csv(
            _require(src, "counterparties", "financing"), FinancingCounterparty
        )
        needs = load_dataclass_csv(_require(src, "needs", "financing"), FundingNeed)
        return counterparties, needs
    raise DataSourceError(f"Unknown data_source type '{src['type']}' for financing.")


def load_asset_allocation(
    request: OptimizationRequest,
) -> tuple[list[AssetClassAssumption], Any]:
    src = _source(request)
    if src["type"] == "simulated":
        return simulate_asset_universe(
            seed=request.context.get("seed", 42),
            context_overrides=request.context,
        )
    if src["type"] == "csv":
        assets = load_dataclass_csv(
            _require(src, "assets", "asset_allocation"),
            AssetClassAssumption,
        )
        covariance = _load_covariance_csv(_require(src, "covariance", "asset_allocation"))
        return assets, covariance
    raise DataSourceError(f"Unknown data_source type '{src['type']}' for asset_allocation.")


def _build_cash_position(
    request: OptimizationRequest,
    src: dict[str, Any],
    funds: list[MoneyMarketFund],
) -> CashPosition:
    """Build the money-market CashPosition from an optional CSV + context."""
    ctx = request.context
    total_cash = ctx.get("total_cash")
    current: dict[str, float] = {}

    # Optional single-row position CSV: total_cash, and per-fund current_* columns
    # are not required — the header may simply carry total_cash and requirements.
    if "position" in src:
        p = Path(src["position"])
        if not p.exists():
            raise DataSourceError(f"position CSV not found: {p}")
        with p.open(newline="") as fh:
            row = next(csv.DictReader(fh), None)
        if row:
            if row.get("total_cash"):
                total_cash = float(row["total_cash"])
            if row.get("daily_liquidity_requirement"):
                ctx = {**ctx, "daily_liquidity_req": float(row["daily_liquidity_requirement"])}
            if row.get("weekly_liquidity_requirement"):
                ctx = {**ctx, "weekly_liquidity_req": float(row["weekly_liquidity_requirement"])}

    if total_cash is None:
        total_cash = sum(f.min_investment for f in funds) or 500_000_000.0

    return CashPosition(
        total_cash=float(total_cash),
        current_allocations=current,
        daily_liquidity_requirement=ctx.get("daily_liquidity_req", 0.30),
        weekly_liquidity_requirement=ctx.get("weekly_liquidity_req", 0.60),
    )


def _load_covariance_csv(path: str | Path) -> Any:
    import numpy as np

    rows: list[list[float]] = []
    p = Path(path)
    if not p.exists():
        raise DataSourceError(f"covariance CSV not found: {p}")
    with p.open(newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if row:
                rows.append([float(value) for value in row])
    covariance = np.array(rows, dtype=float)
    if covariance.ndim != 2 or covariance.shape[0] != covariance.shape[1]:
        raise DataSourceError("asset_allocation covariance CSV must be square.")
    return covariance
