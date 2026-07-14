"""
Simulated money market fund universe and cash position data.

Structure mirrors what a real data layer would provide:
  - funds: available MMFs with yield, expense ratio, liquidity profile
  - cash_position: total investable cash and mandate constraints

Replace with real fund data without changing the optimizer interface.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class MoneyMarketFund:
    fund_id: str
    label: str
    provider: str
    yield_7day: float         # 7-day annualized yield, %
    expense_ratio_bps: float  # basis points
    wam_days: int             # weighted average maturity
    daily_liquidity_pct: float  # fraction redeemable T+0
    weekly_liquidity_pct: float  # fraction redeemable T+0 or T+1
    min_investment: float     # USD
    credit_quality: str       # "government", "prime", "treasury"
    switching_cost_bps: float = 1.0  # cost to move between funds


@dataclass
class CashPosition:
    total_cash: float
    current_allocations: dict[str, float]  # fund_id → USD invested
    daily_liquidity_requirement: float     # must keep T+0 redeemable
    weekly_liquidity_requirement: float


def simulate_universe(
    n_funds: int = 8,
    seed: int = 42,
    context_overrides: dict | None = None,
) -> tuple[list[MoneyMarketFund], CashPosition]:
    rng = random.Random(seed)
    overrides = context_overrides or {}

    providers = ["BlackRock", "Fidelity", "Vanguard", "JPMorgan", "Goldman", "BNY Mellon"]
    credit_types = ["government", "government", "prime", "prime", "treasury"]

    funds = []
    for i in range(n_funds):
        ctype = rng.choice(credit_types)
        if ctype == "treasury":
            yield_range = (4.8, 5.1)
            expense = rng.uniform(3, 8)
            wam = rng.randint(20, 45)
            dl = rng.uniform(0.90, 1.0)
            wl = 1.0
        elif ctype == "government":
            yield_range = (4.9, 5.3)
            expense = rng.uniform(5, 15)
            wam = rng.randint(30, 60)
            dl = rng.uniform(0.75, 0.95)
            wl = rng.uniform(0.95, 1.0)
        else:  # prime
            yield_range = (5.1, 5.6)
            expense = rng.uniform(15, 30)
            wam = rng.randint(40, 90)
            dl = rng.uniform(0.50, 0.80)
            wl = rng.uniform(0.80, 0.95)

        net_yield = rng.uniform(*yield_range) - expense / 100
        net_yield *= overrides.get("yield_shift", 1.0)

        funds.append(
            MoneyMarketFund(
                fund_id=f"MMF_{i:03d}",
                label=f"{rng.choice(providers)} {ctype.title()} Fund {i+1}",
                provider=rng.choice(providers),
                yield_7day=round(net_yield, 4),
                expense_ratio_bps=round(expense, 1),
                wam_days=wam,
                daily_liquidity_pct=round(dl, 4),
                weekly_liquidity_pct=round(wl, 4),
                min_investment=rng.choice([100_000, 500_000, 1_000_000]),
                credit_quality=ctype,
                switching_cost_bps=rng.uniform(0.5, 2.0),
            )
        )

    total_cash = overrides.get("total_cash", 500_000_000)
    # Current allocation: roughly equal spread across existing funds
    n_current = min(3, n_funds)
    current = {funds[i].fund_id: total_cash / n_current for i in range(n_current)}

    position = CashPosition(
        total_cash=total_cash,
        current_allocations=current,
        daily_liquidity_requirement=overrides.get("daily_liquidity_req", 0.30),
        weekly_liquidity_requirement=overrides.get("weekly_liquidity_req", 0.60),
    )
    return funds, position
