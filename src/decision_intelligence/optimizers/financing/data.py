"""
Simulated financing universe: counterparties, instruments, and funding needs.

Structure mirrors real data:
  - counterparties: available financing sources with spread, limit, tenor
  - funding_needs: positions requiring external financing by instrument

Replace with real data adapters without changing the optimizer interface.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class FinancingCounterparty:
    counterparty_id: str
    name: str
    instrument: str             # "repo", "sec_lending", "term_loan", "revolver"
    spread_bps: float           # spread over SOFR / benchmark
    capacity: float             # USD maximum
    min_tenor_days: int
    max_tenor_days: int
    capital_usage_pct: float    # RWA / balance sheet cost as % of notional
    eligible_collateral: list[str] = field(default_factory=list)


@dataclass
class FundingNeed:
    position_id: str
    instrument_type: str
    notional: float
    required_tenor_days: int
    preferred_instrument: str   # "repo", "sec_lending", etc.


def simulate_financing_universe(
    n_counterparties: int = 10,
    seed: int = 42,
    context_overrides: dict | None = None,
) -> tuple[list[FinancingCounterparty], list[FundingNeed]]:
    rng = random.Random(seed)
    overrides = context_overrides or {}

    instruments = ["repo", "repo", "sec_lending", "term_loan", "revolver"]
    cp_names = [
        "Bank Alpha", "Bank Beta", "Prime Broker A", "Prime Broker B",
        "Hedge Fund X", "Insurance Co Y", "Pension Fund Z",
        "Bank Gamma", "Bank Delta", "Custodian A",
    ]

    counterparties = []
    for i in range(n_counterparties):
        instr = rng.choice(instruments)
        if instr == "repo":
            spread = rng.uniform(2, 15)
            capacity = rng.uniform(50e6, 500e6)
            tenor_range = (1, 90)
            cap_pct = rng.uniform(0.5, 2.0)
            collateral = rng.sample(["govt_bond", "corp_bond", "equity", "cash"], k=rng.randint(1, 3))
        elif instr == "sec_lending":
            spread = rng.uniform(10, 40)
            capacity = rng.uniform(20e6, 200e6)
            tenor_range = (1, 30)
            cap_pct = rng.uniform(1.0, 3.0)
            collateral = ["equity", "corp_bond"]
        elif instr == "term_loan":
            spread = rng.uniform(50, 150)
            capacity = rng.uniform(10e6, 100e6)
            tenor_range = (30, 365)
            cap_pct = rng.uniform(5.0, 15.0)
            collateral = []
        else:  # revolver
            spread = rng.uniform(30, 80)
            capacity = rng.uniform(25e6, 150e6)
            tenor_range = (1, 180)
            cap_pct = rng.uniform(2.0, 8.0)
            collateral = []

        capacity *= overrides.get("capacity_scale", 1.0)
        spread *= overrides.get("spread_shift", 1.0)

        counterparties.append(
            FinancingCounterparty(
                counterparty_id=f"CP_{i:03d}",
                name=cp_names[i % len(cp_names)],
                instrument=instr,
                spread_bps=round(spread, 2),
                capacity=round(capacity, 0),
                min_tenor_days=tenor_range[0],
                max_tenor_days=tenor_range[1],
                capital_usage_pct=round(cap_pct, 3),
                eligible_collateral=collateral,
            )
        )

    # Funding needs
    total_need = overrides.get("total_funding_need", 300_000_000)
    needs = [
        FundingNeed("POS_001", "equity_long", total_need * 0.40, 30, "repo"),
        FundingNeed("POS_002", "bond_long", total_need * 0.35, 90, "repo"),
        FundingNeed("POS_003", "mixed", total_need * 0.25, 7, "sec_lending"),
    ]
    return counterparties, needs
