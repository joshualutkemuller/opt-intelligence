"""Tests for the optimizer registry."""

import pytest

from decision_intelligence.optimization.registry import OptimizerRegistry
from decision_intelligence.optimizers import (
    CollateralOptimizer,
    FinancingOptimizer,
    MoneyMarketOptimizer,
)


def make_registry() -> OptimizerRegistry:
    reg = OptimizerRegistry()
    reg.register(CollateralOptimizer())
    reg.register(MoneyMarketOptimizer())
    reg.register(FinancingOptimizer())
    return reg


def test_register_and_list():
    reg = make_registry()
    assert set(reg.list_domains()) == {"collateral", "money_market", "financing"}


def test_get_known_domain():
    reg = make_registry()
    opt = reg.get("collateral")
    assert opt.domain == "collateral"
    assert opt.name == "Collateral Optimizer"


def test_get_unknown_domain_raises():
    reg = make_registry()
    with pytest.raises(KeyError, match="No optimizer registered"):
        reg.get("treasury")


def test_duplicate_registration_raises():
    reg = OptimizerRegistry()
    reg.register(CollateralOptimizer())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(CollateralOptimizer())


def test_contains():
    reg = make_registry()
    assert "collateral" in reg
    assert "treasury" not in reg


def test_len():
    reg = make_registry()
    assert len(reg) == 3
