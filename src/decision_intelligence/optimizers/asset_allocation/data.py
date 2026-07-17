"""Simulated multi-asset assumptions for MVO portfolio allocation."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class AssetClassAssumption:
    asset_id: str
    label: str
    asset_class: str
    expected_return: float
    volatility: float
    current_weight: float
    min_weight: float = 0.0
    max_weight: float = 0.45
    metadata: dict[str, str] = field(default_factory=dict)


def simulate_asset_universe(
    *,
    seed: int = 42,
    context_overrides: dict | None = None,
) -> tuple[list[AssetClassAssumption], np.ndarray]:
    """Return stable annualized return/risk assumptions and covariance matrix."""

    _ = seed  # Kept for API symmetry and future stochastic assumptions.
    overrides = context_overrides or {}
    return_shift = float(overrides.get("return_shift", 0.0))
    volatility_scale = float(overrides.get("volatility_scale", 1.0))
    equity_return_shift = float(overrides.get("equity_return_shift", 0.0))
    bond_return_shift = float(overrides.get("bond_return_shift", 0.0))

    assets = [
        AssetClassAssumption(
            "US_EQ",
            "US Equity",
            "equity",
            0.075 + equity_return_shift + return_shift,
            0.165 * volatility_scale,
            0.36,
            max_weight=0.45,
            metadata={"liquidity": "high"},
        ),
        AssetClassAssumption(
            "INTL_EQ",
            "International Equity",
            "equity",
            0.068 + equity_return_shift + return_shift,
            0.185 * volatility_scale,
            0.18,
            max_weight=0.35,
            metadata={"liquidity": "high"},
        ),
        AssetClassAssumption(
            "CORE_BOND",
            "Core Bonds",
            "fixed_income",
            0.038 + bond_return_shift + return_shift,
            0.060 * volatility_scale,
            0.26,
            max_weight=0.55,
            metadata={"duration": "intermediate"},
        ),
        AssetClassAssumption(
            "HIGH_YIELD",
            "High Yield Credit",
            "credit",
            0.062 + bond_return_shift + return_shift,
            0.105 * volatility_scale,
            0.08,
            max_weight=0.20,
            metadata={"liquidity": "medium"},
        ),
        AssetClassAssumption(
            "REAL_ASSETS",
            "Real Assets",
            "real_assets",
            0.055 + return_shift,
            0.130 * volatility_scale,
            0.07,
            max_weight=0.18,
            metadata={"inflation_sensitivity": "positive"},
        ),
        AssetClassAssumption(
            "CASH",
            "Cash",
            "cash",
            0.030 + return_shift,
            0.010 * volatility_scale,
            0.05,
            min_weight=float(overrides.get("min_cash_weight", 0.02)),
            max_weight=0.25,
            metadata={"liquidity": "daily"},
        ),
    ]

    max_single = overrides.get("max_single_asset_weight")
    if max_single is not None:
        cap = float(max_single)
        assets = [
            AssetClassAssumption(
                asset.asset_id,
                asset.label,
                asset.asset_class,
                asset.expected_return,
                asset.volatility,
                asset.current_weight,
                asset.min_weight,
                min(asset.max_weight, cap),
                asset.metadata,
            )
            for asset in assets
        ]

    correlations = np.array(
        [
            [1.00, 0.82, -0.20, 0.58, 0.52, 0.00],
            [0.82, 1.00, -0.15, 0.60, 0.55, 0.00],
            [-0.20, -0.15, 1.00, 0.25, 0.05, 0.10],
            [0.58, 0.60, 0.25, 1.00, 0.35, 0.05],
            [0.52, 0.55, 0.05, 0.35, 1.00, 0.00],
            [0.00, 0.00, 0.10, 0.05, 0.00, 1.00],
        ]
    )
    vol = np.array([asset.volatility for asset in assets])
    covariance = correlations * np.outer(vol, vol)
    return assets, covariance
