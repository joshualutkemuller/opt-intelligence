"""Tests for the configurable data-provider layer (simulated + CSV)."""

import csv

import pytest

from decision_intelligence.contracts import (
    Objective,
    ObjectiveDirection,
    OptimizationRequest,
)
from decision_intelligence.contracts.results import SolveStatus
from decision_intelligence.data import (
    DataSourceError,
    load_collateral,
    load_dataclass_csv,
    load_financing,
    load_money_market,
)
from decision_intelligence.governance.audit import AuditLog
from decision_intelligence.optimization import OptimizationOrchestrator, OptimizerRegistry
from decision_intelligence.optimizers import (
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)
from decision_intelligence.optimizers.collateral.data import (
    CollateralAsset,
    simulate_inventory,
)
from decision_intelligence.optimizers.financing.data import simulate_financing_universe
from decision_intelligence.optimizers.money_market.data import simulate_universe


def _dump_dataclasses(path, rows):
    from dataclasses import asdict, fields

    cols = [f.name for f in fields(rows[0])]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            d = asdict(r)
            for k, v in d.items():
                if isinstance(v, list):
                    d[k] = ";".join(map(str, v))
            w.writerow(d)


def _req(domain, direction, metric, ctx):
    return OptimizationRequest(
        domain=domain,
        portfolio_id="PORT_T",
        objective=Objective(name=f"{direction.value}_{metric}", direction=direction, metric=metric),
        context=ctx,
    )


# --------------------------------------------------------------------------- #
# Generic CSV coercion
# --------------------------------------------------------------------------- #
def test_load_dataclass_csv_coerces_types(tmp_path):
    assets, _ = simulate_inventory(n_assets=5, seed=1)
    p = tmp_path / "assets.csv"
    _dump_dataclasses(p, assets)
    loaded = load_dataclass_csv(p, CollateralAsset)
    assert len(loaded) == 5
    a = loaded[0]
    assert isinstance(a.market_value, float)
    assert isinstance(a.eligible, bool)
    assert isinstance(a.funding_cost_bps, float)


def test_load_dataclass_csv_missing_required_column(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("asset_id,label\nA1,foo\n")
    with pytest.raises(DataSourceError, match="missing required columns"):
        load_dataclass_csv(p, CollateralAsset)


def test_load_dataclass_csv_missing_file(tmp_path):
    with pytest.raises(DataSourceError, match="not found"):
        load_dataclass_csv(tmp_path / "nope.csv", CollateralAsset)


def test_list_field_roundtrips(tmp_path):
    cps, _ = simulate_financing_universe(n_counterparties=6, seed=3)
    from decision_intelligence.optimizers.financing.data import FinancingCounterparty

    p = tmp_path / "cps.csv"
    _dump_dataclasses(p, cps)
    loaded = load_dataclass_csv(p, FinancingCounterparty)
    assert all(isinstance(c.eligible_collateral, list) for c in loaded)


# --------------------------------------------------------------------------- #
# Simulated default (backward compatibility)
# --------------------------------------------------------------------------- #
def test_default_source_is_simulated():
    req = _req("money_market", ObjectiveDirection.MAXIMIZE, "yield", {"seed": 42})
    funds, position = load_money_market(req)
    ref_funds, _ = simulate_universe(n_funds=8, seed=42)
    assert [f.fund_id for f in funds] == [f.fund_id for f in ref_funds]


def test_unknown_source_type_raises():
    req = _req("collateral", ObjectiveDirection.MINIMIZE, "funding_cost",
               {"data_source": {"type": "sql"}})
    with pytest.raises(DataSourceError, match="Unknown data_source type"):
        load_collateral(req)


def test_csv_source_missing_path_key_raises():
    # No 'counterparties' key at all → _require fails before any file access.
    req = _req("financing", ObjectiveDirection.MINIMIZE, "funding_spread",
               {"data_source": {"type": "csv"}})
    with pytest.raises(DataSourceError, match="requires a 'counterparties' path"):
        load_financing(req)


# --------------------------------------------------------------------------- #
# CSV → orchestrator end-to-end, all three domains
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def csv_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("csv")
    funds, _ = simulate_universe(n_funds=8, seed=7)
    _dump_dataclasses(d / "funds.csv", funds)
    with open(d / "pos.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["total_cash", "daily_liquidity_requirement", "weekly_liquidity_requirement"])
        w.writerow([500_000_000, 0.30, 0.60])

    assets, obls = simulate_inventory(n_assets=15, seed=7)
    _dump_dataclasses(d / "assets.csv", assets)
    _dump_dataclasses(d / "obls.csv", obls)

    cps, needs = simulate_financing_universe(n_counterparties=10, seed=7)
    _dump_dataclasses(d / "cps.csv", cps)
    _dump_dataclasses(d / "needs.csv", needs)
    return d


def _orch():
    reg = OptimizerRegistry()
    reg.register(CollateralOptimizer())
    reg.register(MoneyMarketOptimizer())
    reg.register(FinancingOptimizer())
    return OptimizationOrchestrator(reg, AuditLog())


def test_money_market_from_csv_solves(csv_dir):
    req = _req("money_market", ObjectiveDirection.MAXIMIZE, "yield", {
        "data_source": {
            "type": "csv",
            "funds": str(csv_dir / "funds.csv"),
            "position": str(csv_dir / "pos.csv"),
        }
    })
    result = _orch().run(req)
    assert result.status == SolveStatus.OPTIMAL
    assert result.allocations


def test_collateral_from_csv_solves(csv_dir):
    req = _req("collateral", ObjectiveDirection.MINIMIZE, "funding_cost", {
        "data_source": {
            "type": "csv",
            "assets": str(csv_dir / "assets.csv"),
            "obligations": str(csv_dir / "obls.csv"),
        }
    })
    result = _orch().run(req)
    assert result.status == SolveStatus.OPTIMAL
    assert result.allocations


def test_financing_from_csv_solves(csv_dir):
    req = _req("financing", ObjectiveDirection.MINIMIZE, "funding_spread", {
        "data_source": {
            "type": "csv",
            "counterparties": str(csv_dir / "cps.csv"),
            "needs": str(csv_dir / "needs.csv"),
        }
    })
    result = _orch().run(req)
    assert result.status == SolveStatus.OPTIMAL
    assert result.allocations
