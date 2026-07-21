"""Data quality check layer for production optimizer data sources.

Each check is a named callable registered in ``_REGISTRY``.  Checks receive a
list of dataclass instances (from the simulator) *or* a list of plain dicts
(from a CSV reader) — they use ``_get`` to abstract the difference.

Adapters and loaders call ``run_quality_checks`` with the list of check names
declared in ``DataContractSpec.quality_checks`` to enforce them before any
data reaches the solver.

Adding a new check:

    @register("my check name as declared in the config")
    def _my_check(rows: list, dataset: str) -> DataQualityResult:
        violations = []
        for row in rows:
            value = _get(row, "my_field")
            if value is not None and value < 0:
                violations.append(DataQualityViolation(
                    check="my check name as declared in the config",
                    record_id=str(_get(row, "asset_id") or _get(row, "fund_id") or "?"),
                    field="my_field",
                    observed=value,
                    message=f"my_field must be nonnegative, got {value!r}",
                ))
        return DataQualityResult(
            check="my check name as declared in the config",
            dataset=dataset,
            passed=not violations,
            violations=violations,
        )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #

@dataclass
class DataQualityViolation:
    check: str
    record_id: str | None
    field: str | None
    observed: Any
    message: str


@dataclass
class DataQualityResult:
    check: str
    dataset: str
    passed: bool
    violations: list[DataQualityViolation] = field(default_factory=list)


@dataclass
class DataQualityReport:
    dataset: str
    check_names: list[str]
    results: list[DataQualityResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def violations(self) -> list[DataQualityViolation]:
        return [v for r in self.results for v in r.violations]

    @property
    def blocking_issues(self) -> list[str]:
        return [v.message for r in self.results if not r.passed for v in r.violations]

    @property
    def unknown_checks(self) -> list[str]:
        return [r.check for r in self.results if r.check not in _REGISTRY]


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

CheckFn = Callable[[list[Any], str], DataQualityResult]
_REGISTRY: dict[str, CheckFn] = {}


def register(name: str) -> Callable[[CheckFn], CheckFn]:
    """Decorator that registers a quality check function under ``name``."""
    def decorator(fn: CheckFn) -> CheckFn:
        _REGISTRY[name] = fn
        return fn
    return decorator


def run_quality_checks(
    rows: list[Any],
    check_names: list[str],
    dataset: str,
) -> DataQualityReport:
    """Run named quality checks against ``rows`` and return a structured report.

    Unknown check names produce a passing result with a note — this keeps the
    system forward-compatible when configs reference checks not yet implemented.
    """
    results: list[DataQualityResult] = []
    for name in check_names:
        fn = _REGISTRY.get(name)
        if fn is None:
            results.append(DataQualityResult(
                check=name,
                dataset=dataset,
                passed=True,
                violations=[
                    DataQualityViolation(
                        check=name,
                        record_id=None,
                        field=None,
                        observed=None,
                        message=f"Quality check '{name}' is not registered — skipped.",
                    )
                ],
            ))
        else:
            results.append(fn(rows, dataset))
    return DataQualityReport(dataset=dataset, check_names=check_names, results=results)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _get(row: Any, field_name: str) -> Any:
    """Get a field from a dataclass instance or a plain dict."""
    if isinstance(row, dict):
        return row.get(field_name)
    return getattr(row, field_name, None)


def _row_id(row: Any) -> str:
    """Return a stable display identifier for a data row."""
    for candidate in ("asset_id", "fund_id", "obligation_id", "counterparty_id",
                      "need_id", "asset_class", "counterparty", "id"):
        value = _get(row, candidate)
        if value is not None:
            return str(value)
    return "?"


# --------------------------------------------------------------------------- #
# Collateral checks
# --------------------------------------------------------------------------- #

@register("market values are nonnegative")
def _check_market_values_nonnegative(rows: list[Any], dataset: str) -> DataQualityResult:
    violations: list[DataQualityViolation] = []
    for row in rows:
        value = _get(row, "market_value")
        if value is not None and float(value) < 0:
            violations.append(DataQualityViolation(
                check="market values are nonnegative",
                record_id=_row_id(row),
                field="market_value",
                observed=value,
                message=(
                    f"{dataset}/{_row_id(row)}: market_value must be >= 0, got {value!r}"
                ),
            ))
    return DataQualityResult(
        check="market values are nonnegative",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )


@register("haircuts are between 0 and 1")
def _check_haircuts_bounds(rows: list[Any], dataset: str) -> DataQualityResult:
    violations: list[DataQualityViolation] = []
    for row in rows:
        value = _get(row, "haircut")
        if value is None:
            continue
        fv = float(value)
        if not (0.0 <= fv <= 1.0):
            violations.append(DataQualityViolation(
                check="haircuts are between 0 and 1",
                record_id=_row_id(row),
                field="haircut",
                observed=value,
                message=(
                    f"{dataset}/{_row_id(row)}: haircut must be in [0, 1], got {value!r}"
                ),
            ))
    return DataQualityResult(
        check="haircuts are between 0 and 1",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )


@register("each obligation has at least one eligible asset class")
def _check_obligations_have_eligible_classes(rows: list[Any], dataset: str) -> DataQualityResult:
    violations: list[DataQualityViolation] = []
    for row in rows:
        classes = _get(row, "eligible_asset_classes")
        if classes is None:
            continue
        # Handles both list (dataclass) and semicolon-delimited string (CSV)
        if isinstance(classes, str):
            classes = [c.strip() for c in classes.split(";") if c.strip()]
        if len(classes) == 0:
            violations.append(DataQualityViolation(
                check="each obligation has at least one eligible asset class",
                record_id=_row_id(row),
                field="eligible_asset_classes",
                observed=classes,
                message=(
                    f"{dataset}/{_row_id(row)}: eligible_asset_classes must not be empty"
                ),
            ))
    return DataQualityResult(
        check="each obligation has at least one eligible asset class",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )


@register("at least one eligible asset exists")
def _check_at_least_one_eligible_asset(rows: list[Any], dataset: str) -> DataQualityResult:
    eligible_count = sum(
        1 for row in rows
        if _get(row, "eligible") not in (False, "false", "0", "no", "n")
        and _get(row, "eligible") is not None
    )
    if eligible_count == 0:
        return DataQualityResult(
            check="at least one eligible asset exists",
            dataset=dataset,
            passed=False,
            violations=[
                DataQualityViolation(
                    check="at least one eligible asset exists",
                    record_id=None,
                    field="eligible",
                    observed=0,
                    message=f"{dataset}: no eligible assets found in {len(rows)} rows",
                )
            ],
        )
    return DataQualityResult(
        check="at least one eligible asset exists",
        dataset=dataset,
        passed=True,
    )


@register("funding cost is nonnegative")
def _check_funding_cost_nonnegative(rows: list[Any], dataset: str) -> DataQualityResult:
    violations: list[DataQualityViolation] = []
    for row in rows:
        value = _get(row, "funding_cost_bps")
        if value is not None and float(value) < 0:
            violations.append(DataQualityViolation(
                check="funding cost is nonnegative",
                record_id=_row_id(row),
                field="funding_cost_bps",
                observed=value,
                message=(
                    f"{dataset}/{_row_id(row)}: funding_cost_bps must be >= 0, got {value!r}"
                ),
            ))
    return DataQualityResult(
        check="funding cost is nonnegative",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )


# --------------------------------------------------------------------------- #
# Money-market checks
# --------------------------------------------------------------------------- #

@register("fund yields are nonnegative")
def _check_fund_yields_nonnegative(rows: list[Any], dataset: str) -> DataQualityResult:
    violations: list[DataQualityViolation] = []
    for row in rows:
        value = _get(row, "gross_yield")
        if value is not None and float(value) < 0:
            violations.append(DataQualityViolation(
                check="fund yields are nonnegative",
                record_id=_row_id(row),
                field="gross_yield",
                observed=value,
                message=(
                    f"{dataset}/{_row_id(row)}: gross_yield must be >= 0, got {value!r}"
                ),
            ))
    return DataQualityResult(
        check="fund yields are nonnegative",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )


@register("liquidity ratios are between 0 and 1")
def _check_liquidity_ratios_bounds(rows: list[Any], dataset: str) -> DataQualityResult:
    violations: list[DataQualityViolation] = []
    for row in rows:
        for field_name in ("daily_liquidity", "weekly_liquidity"):
            value = _get(row, field_name)
            if value is None:
                continue
            fv = float(value)
            if not (0.0 <= fv <= 1.0):
                violations.append(DataQualityViolation(
                    check="liquidity ratios are between 0 and 1",
                    record_id=_row_id(row),
                    field=field_name,
                    observed=value,
                    message=(
                        f"{dataset}/{_row_id(row)}: {field_name} must be in [0, 1], "
                        f"got {value!r}"
                    ),
                ))
    return DataQualityResult(
        check="liquidity ratios are between 0 and 1",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )


@register("minimum investments are nonnegative")
def _check_min_investments_nonnegative(rows: list[Any], dataset: str) -> DataQualityResult:
    violations: list[DataQualityViolation] = []
    for row in rows:
        value = _get(row, "min_investment")
        if value is not None and float(value) < 0:
            violations.append(DataQualityViolation(
                check="minimum investments are nonnegative",
                record_id=_row_id(row),
                field="min_investment",
                observed=value,
                message=(
                    f"{dataset}/{_row_id(row)}: min_investment must be >= 0, got {value!r}"
                ),
            ))
    return DataQualityResult(
        check="minimum investments are nonnegative",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )


@register("fund WAM within statutory limit")
def _check_fund_wam_statutory(rows: list[Any], dataset: str) -> DataQualityResult:
    _STATUTORY_WAM_DAYS = 60
    violations: list[DataQualityViolation] = []
    for row in rows:
        value = _get(row, "wam_days")
        if value is not None and float(value) > _STATUTORY_WAM_DAYS:
            violations.append(DataQualityViolation(
                check="fund WAM within statutory limit",
                record_id=_row_id(row),
                field="wam_days",
                observed=value,
                message=(
                    f"{dataset}/{_row_id(row)}: wam_days {value} exceeds statutory "
                    f"limit of {_STATUTORY_WAM_DAYS} days"
                ),
            ))
    return DataQualityResult(
        check="fund WAM within statutory limit",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )


# --------------------------------------------------------------------------- #
# Financing checks
# --------------------------------------------------------------------------- #

@register("counterparty capacity is nonnegative")
def _check_counterparty_capacity_nonnegative(rows: list[Any], dataset: str) -> DataQualityResult:
    violations: list[DataQualityViolation] = []
    for row in rows:
        value = _get(row, "max_capacity")
        if value is not None and float(value) < 0:
            violations.append(DataQualityViolation(
                check="counterparty capacity is nonnegative",
                record_id=_row_id(row),
                field="max_capacity",
                observed=value,
                message=(
                    f"{dataset}/{_row_id(row)}: max_capacity must be >= 0, got {value!r}"
                ),
            ))
    return DataQualityResult(
        check="counterparty capacity is nonnegative",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )


@register("financing spread is nonnegative")
def _check_financing_spread_nonnegative(rows: list[Any], dataset: str) -> DataQualityResult:
    violations: list[DataQualityViolation] = []
    for row in rows:
        value = _get(row, "spread_bps")
        if value is not None and float(value) < 0:
            violations.append(DataQualityViolation(
                check="financing spread is nonnegative",
                record_id=_row_id(row),
                field="spread_bps",
                observed=value,
                message=(
                    f"{dataset}/{_row_id(row)}: spread_bps must be >= 0, got {value!r}"
                ),
            ))
    return DataQualityResult(
        check="financing spread is nonnegative",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )


@register("funding needs are positive")
def _check_funding_needs_positive(rows: list[Any], dataset: str) -> DataQualityResult:
    violations: list[DataQualityViolation] = []
    for row in rows:
        value = _get(row, "amount")
        if value is not None and float(value) <= 0:
            violations.append(DataQualityViolation(
                check="funding needs are positive",
                record_id=_row_id(row),
                field="amount",
                observed=value,
                message=(
                    f"{dataset}/{_row_id(row)}: funding need amount must be > 0, got {value!r}"
                ),
            ))
    return DataQualityResult(
        check="funding needs are positive",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )


# --------------------------------------------------------------------------- #
# Asset-allocation checks
# --------------------------------------------------------------------------- #

@register("nonnegative_market_value")
def _check_nonnegative_market_value(rows: list[Any], dataset: str) -> DataQualityResult:
    """Alias used in asset-allocation config; delegates to the generic check."""
    return _check_market_values_nonnegative(rows, dataset)


@register("expected returns are finite")
def _check_expected_returns_finite(rows: list[Any], dataset: str) -> DataQualityResult:
    import math
    violations: list[DataQualityViolation] = []
    for row in rows:
        value = _get(row, "expected_return")
        if value is not None and not math.isfinite(float(value)):
            violations.append(DataQualityViolation(
                check="expected returns are finite",
                record_id=_row_id(row),
                field="expected_return",
                observed=value,
                message=(
                    f"{dataset}/{_row_id(row)}: expected_return must be finite, got {value!r}"
                ),
            ))
    return DataQualityResult(
        check="expected returns are finite",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )


@register("volatilities are positive")
def _check_volatilities_positive(rows: list[Any], dataset: str) -> DataQualityResult:
    violations: list[DataQualityViolation] = []
    for row in rows:
        value = _get(row, "annual_volatility")
        if value is not None and float(value) <= 0:
            violations.append(DataQualityViolation(
                check="volatilities are positive",
                record_id=_row_id(row),
                field="annual_volatility",
                observed=value,
                message=(
                    f"{dataset}/{_row_id(row)}: annual_volatility must be > 0, got {value!r}"
                ),
            ))
    return DataQualityResult(
        check="volatilities are positive",
        dataset=dataset,
        passed=not violations,
        violations=violations,
    )
