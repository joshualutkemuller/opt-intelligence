"""
Simulated collateral inventory and obligation data.

Structure mirrors what a real data layer would provide:
  - assets: inventory of eligible collateral with haircut, cost, and eligibility flags
  - obligations: counterparty margin/collateral calls that must be satisfied
  - concentration_limits: per-asset-class max as fraction of total obligation

Replace this module with real data adapters without changing the optimizer interface.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class CollateralAsset:
    asset_id: str
    label: str
    asset_class: str          # e.g. "govt_bond", "corp_bond", "equity", "cash"
    market_value: float       # USD
    haircut: float            # fraction, e.g. 0.02 = 2%
    funding_cost_bps: float   # basis points per annum
    eligible: bool = True
    currency: str = "USD"
    rating: str = "AAA"
    maturity_years: float = 5.0


@dataclass
class CollateralObligation:
    obligation_id: str
    counterparty: str
    required_value: float     # USD, post-haircut
    eligible_asset_classes: list[str] = field(default_factory=list)
    venue_type: str = "bilateral"      # bilateral, ccp, exchange
    agreement_type: str = "CSA"        # CSA, cleared swap, futures margin, exchange margin


def simulate_inventory(
    n_assets: int = 20,
    seed: int = 42,
    context_overrides: dict | None = None,
) -> tuple[list[CollateralAsset], list[CollateralObligation]]:
    """Generate a reproducible simulated collateral inventory and obligations."""
    rng = random.Random(seed)
    overrides = context_overrides or {}

    asset_classes = ["govt_bond", "govt_bond", "corp_bond", "corp_bond", "equity", "cash"]
    ratings_by_class = {
        "govt_bond": ["AAA", "AA+"],
        "corp_bond": ["A", "A-", "BBB+"],
        "equity": ["NR"],
        "cash": ["AAA"],
    }
    haircuts_by_class = {
        "govt_bond": (0.01, 0.03),
        "corp_bond": (0.05, 0.10),
        "equity": (0.15, 0.25),
        "cash": (0.00, 0.00),
    }
    funding_cost_by_class = {
        "govt_bond": (5, 20),
        "corp_bond": (20, 60),
        "equity": (50, 120),
        "cash": (0, 5),
    }

    assets = []
    for i in range(n_assets):
        ac = rng.choice(asset_classes)
        hc_lo, hc_hi = haircuts_by_class[ac]
        fc_lo, fc_hi = funding_cost_by_class[ac]
        mv = rng.uniform(5e6, 50e6) * overrides.get("inventory_scale", 1.0)
        assets.append(
            CollateralAsset(
                asset_id=f"ASSET_{i:03d}",
                label=f"{ac.replace('_', ' ').title()} {i+1}",
                asset_class=ac,
                market_value=round(mv, 2),
                haircut=round(rng.uniform(hc_lo, hc_hi), 4),
                funding_cost_bps=round(rng.uniform(fc_lo, fc_hi), 1),
                eligible=rng.random() > 0.1,
                rating=rng.choice(ratings_by_class[ac]),
                maturity_years=round(rng.uniform(0.25, 30.0), 2),
            )
        )

    # Multiple realistic collateral demands: bilateral CSAs plus cleared
    # derivatives and exchange margin. Required values are post-haircut.
    obligation_scale = overrides.get("obligation_scale", 1.0)
    obligations = [
        CollateralObligation(
            obligation_id="OBL_001",
            counterparty="Dealer A Bilateral CSA",
            required_value=30e6 * obligation_scale,
            eligible_asset_classes=["govt_bond", "corp_bond", "cash"],
            venue_type="bilateral",
            agreement_type="ISDA CSA",
        ),
        CollateralObligation(
            obligation_id="OBL_002",
            counterparty="Dealer B Bilateral CSA",
            required_value=20e6 * obligation_scale,
            eligible_asset_classes=["govt_bond", "cash"],
            venue_type="bilateral",
            agreement_type="ISDA CSA",
        ),
        CollateralObligation(
            obligation_id="OBL_003",
            counterparty="Dealer C Bilateral CSA",
            required_value=15e6 * obligation_scale,
            eligible_asset_classes=["govt_bond", "corp_bond", "equity", "cash"],
            venue_type="bilateral",
            agreement_type="ISDA CSA",
        ),
        CollateralObligation(
            obligation_id="OBL_004",
            counterparty="LCH SwapClear",
            required_value=25e6 * obligation_scale,
            eligible_asset_classes=["govt_bond", "corp_bond", "cash"],
            venue_type="ccp",
            agreement_type="cleared swaps initial margin",
        ),
        CollateralObligation(
            obligation_id="OBL_005",
            counterparty="CME Futures Exchange",
            required_value=10e6 * obligation_scale,
            eligible_asset_classes=["govt_bond", "corp_bond", "cash"],
            venue_type="exchange",
            agreement_type="futures variation margin",
        ),
    ]
    return assets, obligations
