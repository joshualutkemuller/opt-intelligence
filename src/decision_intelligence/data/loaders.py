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
    raise DataSourceError(f"Unknown data_source type '{src['type']}' for collateral.")


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
