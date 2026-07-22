"""Tests for the data quality check layer (quality.py) and its integration points."""

from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path

import pytest

from decision_intelligence.data.quality import (
    DataQualityReport,
    DataQualityViolation,
    run_quality_checks,
)


# --------------------------------------------------------------------------- #
# run_quality_checks
# --------------------------------------------------------------------------- #

def test_market_values_nonnegative_pass():
    rows = [{"asset_id": "A1", "market_value": "100.0"}, {"asset_id": "A2", "market_value": "0"}]
    report = run_quality_checks(rows, ["market values are nonnegative"], "collateral_inventory")
    assert report.passed
    assert report.violations == []


def test_market_values_nonnegative_fail():
    rows = [{"asset_id": "A1", "market_value": "-1.0"}]
    report = run_quality_checks(rows, ["market values are nonnegative"], "collateral_inventory")
    assert not report.passed
    assert len(report.violations) == 1
    v = report.violations[0]
    assert v.field == "market_value"
    assert v.record_id == "A1"
    assert "A1" in v.message


def test_haircuts_bounds_fail():
    rows = [{"asset_id": "B1", "haircut": "1.5"}]
    report = run_quality_checks(rows, ["haircuts are between 0 and 1"], "collateral_inventory")
    assert not report.passed
    assert report.violations[0].field == "haircut"


def test_haircuts_bounds_pass_none():
    rows = [{"asset_id": "B2", "market_value": "50"}]  # no haircut field
    report = run_quality_checks(rows, ["haircuts are between 0 and 1"], "collateral_inventory")
    assert report.passed


def test_obligations_eligible_classes_fail():
    rows = [{"obligation_id": "OB1", "eligible_asset_classes": ""}]
    report = run_quality_checks(
        rows, ["each obligation has at least one eligible asset class"], "margin_obligations"
    )
    assert not report.passed


def test_obligations_eligible_classes_pass_list():
    rows = [{"obligation_id": "OB1", "eligible_asset_classes": ["bonds", "equities"]}]
    report = run_quality_checks(
        rows, ["each obligation has at least one eligible asset class"], "margin_obligations"
    )
    assert report.passed


def test_at_least_one_eligible_asset_fail():
    rows = [{"asset_id": "A1", "eligible": "false"}, {"asset_id": "A2", "eligible": None}]
    report = run_quality_checks(rows, ["at least one eligible asset exists"], "collateral_inventory")
    assert not report.passed


def test_at_least_one_eligible_asset_pass():
    rows = [{"asset_id": "A1", "eligible": "true"}]
    report = run_quality_checks(rows, ["at least one eligible asset exists"], "collateral_inventory")
    assert report.passed


def test_fund_wam_statutory_fail():
    rows = [{"fund_id": "F1", "wam_days": "65"}]
    report = run_quality_checks(rows, ["fund WAM within statutory limit"], "money_market_funds")
    assert not report.passed
    assert "60" in report.violations[0].message


def test_fund_wam_statutory_pass():
    rows = [{"fund_id": "F1", "wam_days": "55"}]
    report = run_quality_checks(rows, ["fund WAM within statutory limit"], "money_market_funds")
    assert report.passed


def test_volatilities_positive_fail():
    rows = [{"asset_class": "EQ", "annual_volatility": "0.0"}]
    report = run_quality_checks(rows, ["volatilities are positive"], "asset_universe")
    assert not report.passed


def test_expected_returns_finite_fail():
    import math
    rows = [{"asset_class": "EQ", "expected_return": math.inf}]
    report = run_quality_checks(rows, ["expected returns are finite"], "asset_universe")
    assert not report.passed


def test_unknown_check_name_is_skipped():
    rows = [{"asset_id": "A1"}]
    report = run_quality_checks(rows, ["no such check"], "test_dataset")
    # Unknown checks produce a passing result with a note in the violation message
    assert report.passed
    assert "not registered" in report.violations[0].message


def test_multiple_checks_aggregate_violations():
    rows = [{"asset_id": "A1", "market_value": "-5", "haircut": "2.0"}]
    report = run_quality_checks(
        rows,
        ["market values are nonnegative", "haircuts are between 0 and 1"],
        "collateral_inventory",
    )
    assert not report.passed
    assert len(report.violations) == 2


def test_blocking_issues_property():
    rows = [{"asset_id": "A1", "market_value": "-1"}]
    report = run_quality_checks(rows, ["market values are nonnegative"], "collateral_inventory")
    assert len(report.blocking_issues) == 1
    assert "market_value" in report.blocking_issues[0]


def test_empty_rows_with_aggregate_check():
    rows = []
    report = run_quality_checks(rows, ["at least one eligible asset exists"], "collateral_inventory")
    assert not report.passed


# --------------------------------------------------------------------------- #
# LocalCsvDataAdapter integration
# --------------------------------------------------------------------------- #

def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_local_csv_adapter_runs_quality_checks_and_blocks():
    from decision_intelligence.production_optimizers.data.adapters import LocalCsvDataAdapter
    from decision_intelligence.production_optimizers.data.contracts import DataSourceContract

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "assets.csv"
        _write_csv(csv_path, [
            {"asset_id": "A1", "market_value": "-100", "eligible": "true"},
        ])
        contract = DataSourceContract(
            dataset="collateral_inventory",
            source_type="csv",
            uri=str(csv_path),
            required_columns=["asset_id", "market_value"],
            quality_checks=["market values are nonnegative"],
        )
        report = LocalCsvDataAdapter().inspect(contract)
        assert not report.blocking_issues == []
        assert any("market_value" in issue for issue in report.blocking_issues)


def test_local_csv_adapter_passes_with_valid_data():
    from decision_intelligence.production_optimizers.data.adapters import LocalCsvDataAdapter
    from decision_intelligence.production_optimizers.data.contracts import DataSourceContract

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "assets.csv"
        _write_csv(csv_path, [
            {"asset_id": "A1", "market_value": "100", "eligible": "true"},
        ])
        contract = DataSourceContract(
            dataset="collateral_inventory",
            source_type="csv",
            uri=str(csv_path),
            required_columns=["asset_id", "market_value"],
            quality_checks=["market values are nonnegative"],
        )
        report = LocalCsvDataAdapter().inspect(contract)
        assert report.blocking_issues == []


def test_local_csv_adapter_no_quality_checks_skips_enforcement():
    from decision_intelligence.production_optimizers.data.adapters import LocalCsvDataAdapter
    from decision_intelligence.production_optimizers.data.contracts import DataSourceContract

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "assets.csv"
        _write_csv(csv_path, [
            {"asset_id": "A1", "market_value": "-999"},
        ])
        contract = DataSourceContract(
            dataset="collateral_inventory",
            source_type="csv",
            uri=str(csv_path),
            required_columns=["asset_id", "market_value"],
            quality_checks=[],  # no checks declared
        )
        report = LocalCsvDataAdapter().inspect(contract)
        assert report.blocking_issues == []


# --------------------------------------------------------------------------- #
# DataQualityReport public API
# --------------------------------------------------------------------------- #

def test_report_unknown_checks_property():
    rows = [{"asset_id": "X"}]
    report = run_quality_checks(rows, ["market values are nonnegative", "not a real check"], "ds")
    assert "not a real check" in report.unknown_checks
    assert "market values are nonnegative" not in report.unknown_checks


def test_report_violations_flat_list():
    rows = [{"asset_id": "A1", "market_value": "-1"}, {"asset_id": "A2", "market_value": "-2"}]
    report = run_quality_checks(rows, ["market values are nonnegative"], "collateral_inventory")
    assert len(report.violations) == 2
