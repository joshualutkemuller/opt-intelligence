"""Small deterministic parsers for guided chat answers."""

from __future__ import annotations

import re

DOMAIN_ALIASES = {
    "collateral": "collateral",
    "collateral optimizer": "collateral",
    "money_market": "money_market",
    "money market": "money_market",
    "cash": "money_market",
    "liquidity": "money_market",
    "financing": "financing",
    "funding": "financing",
    "repo": "financing",
    "asset allocation": "asset_allocation",
    "asset_allocation": "asset_allocation",
    "allocation": "asset_allocation",
    "mvo": "asset_allocation",
    "portfolio": "asset_allocation",
}

_AMOUNT_RE = re.compile(r"\$?\s*([\d,.]+)\s*([kmb]|thousand|million|billion)?", re.I)


def detect_domain(text: str) -> str | None:
    normalized = text.lower().replace("-", " ").replace("_", " ")
    for alias, domain in sorted(DOMAIN_ALIASES.items(), key=lambda item: -len(item[0])):
        if alias.replace("_", " ") in normalized:
            return domain
    return None


def detect_scenarios(text: str) -> list[str]:
    normalized = text.lower().replace("-", " ")
    scenarios: list[str] = []

    if "credit" in normalized and "stress" in normalized:
        scenarios.append("credit_stress")
    elif "stress" in normalized or "liquidity shock" in normalized:
        scenarios.append("stress")

    if "downside" in normalized:
        scenarios.append("downside")
    if "inventory" in normalized or "squeeze" in normalized:
        scenarios.append("inventory")
    if "none" in normalized or normalized in {"no", "n"}:
        return []

    return scenarios


def is_yes(text: str) -> bool:
    return text.strip().lower() in {"y", "yes", "confirm", "run", "go", "ok", "okay"}


def is_no(text: str) -> bool:
    return text.strip().lower() in {"n", "no", "cancel", "stop"}


def parse_amount(text: str) -> float:
    match = _AMOUNT_RE.search(text)
    if not match:
        raise ValueError("Enter an amount like 500M, $300 million, or 75000000.")
    value = float(match.group(1).replace(",", ""))
    unit = (match.group(2) or "").lower()
    if unit in {"k", "thousand"}:
        value *= 1_000
    elif unit in {"m", "million"}:
        value *= 1_000_000
    elif unit in {"b", "billion"}:
        value *= 1_000_000_000
    return value


def parse_int(text: str) -> int:
    match = re.search(r"\d+", text.replace(",", ""))
    if not match:
        raise ValueError("Enter a whole number.")
    return int(match.group(0))


def parse_fraction(text: str) -> float:
    raw = text.strip().lower()
    match = re.search(r"[\d.]+", raw)
    if not match:
        raise ValueError("Enter a percentage like 30% or a fraction like 0.30.")
    value = float(match.group(0))
    if "%" in raw or value > 1:
        value /= 100
    if not 0 <= value <= 1:
        raise ValueError("Enter a value between 0% and 100%.")
    return value


def parse_percent_points(text: str) -> float:
    """Parse a percent answer but return percentage points, e.g. 5% -> 5.0."""
    raw = text.strip().lower()
    match = re.search(r"[\d.]+", raw)
    if not match:
        raise ValueError("Enter a percentage like 5%.")
    value = float(match.group(0))
    if value <= 1 and "%" not in raw:
        value *= 100
    return value


def parse_float(text: str) -> float:
    match = re.search(r"-?[\d.]+", text.replace(",", ""))
    if not match:
        raise ValueError("Enter a number.")
    return float(match.group(0))


def parse_scenario_names(text: str) -> list[str]:
    scenarios = detect_scenarios(text)
    if scenarios or is_no(text) or "none" in text.lower():
        return scenarios
    if "liquidity" in text.lower():
        return ["stress"]
    raise ValueError("Enter none, stress, credit stress, downside, or inventory.")


def parse_solver_backend(text: str) -> str:
    normalized = text.strip().lower()
    if "scipy" in normalized or "highs" in normalized:
        return "scipy"
    if "cvx" in normalized:
        return "cvxpy"
    raise ValueError("Enter scipy or cvxpy.")


def parse_problem_type(text: str) -> str:
    normalized = text.strip().lower()
    for problem_type in ("milp", "lp", "qp", "conic"):
        if problem_type in normalized:
            return problem_type
    raise ValueError("Enter lp, milp, qp, or conic.")
