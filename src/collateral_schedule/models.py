"""Data models for counterparty collateral schedules."""

from __future__ import annotations

from enum import Enum
from typing import Any


class MarginType(str, Enum):
    IM = "IM"            # Initial Margin (bilateral/SIMM)
    VM = "VM"            # Variation Margin (CSA)
    REPO = "REPO"        # Repo / reverse repo haircuts
    SBL = "SBL"          # Securities Borrowing & Lending
    CCP_IM = "CCP_IM"    # CCP / exchange initial margin
    HOUSE = "HOUSE"      # Proprietary / house margin
    OTHER = "OTHER"


class AssetClass(str, Enum):
    CASH = "CASH"
    GOVT = "GOVT"           # Government bonds (sovereign)
    AGENCY = "AGENCY"       # Agency / GSE paper
    CORP = "CORP"           # Investment-grade corporate bonds
    HY_CORP = "HY_CORP"     # High-yield corporate
    EQUITY = "EQUITY"       # Listed equities
    ABS = "ABS"             # Asset-backed securities
    MBS = "MBS"             # Mortgage-backed securities
    MUNI = "MUNI"           # Municipal bonds
    MMF = "MMF"             # Money-market fund shares
    COVERED = "COVERED"     # Covered bonds
    OTHER = "OTHER"


# ── Column name aliases for CSV/XLSX parsing ──────────────────────────────────

ASSET_CLASS_ALIASES: dict[str, AssetClass] = {
    "cash": AssetClass.CASH,
    "government": AssetClass.GOVT,
    "govt": AssetClass.GOVT,
    "sovereign": AssetClass.GOVT,
    "treasury": AssetClass.GOVT,
    "treasuries": AssetClass.GOVT,
    "agency": AssetClass.AGENCY,
    "gse": AssetClass.AGENCY,
    "corporate": AssetClass.CORP,
    "corp": AssetClass.CORP,
    "investment grade": AssetClass.CORP,
    "ig corp": AssetClass.CORP,
    "high yield": AssetClass.HY_CORP,
    "hy": AssetClass.HY_CORP,
    "equity": AssetClass.EQUITY,
    "equities": AssetClass.EQUITY,
    "stock": AssetClass.EQUITY,
    "abs": AssetClass.ABS,
    "asset backed": AssetClass.ABS,
    "mbs": AssetClass.MBS,
    "mortgage": AssetClass.MBS,
    "muni": AssetClass.MUNI,
    "municipal": AssetClass.MUNI,
    "mmf": AssetClass.MMF,
    "money market": AssetClass.MMF,
    "money market fund": AssetClass.MMF,
    "covered": AssetClass.COVERED,
    "covered bond": AssetClass.COVERED,
}

# Canonical column names → possible header spellings in source files
COLUMN_ALIASES: dict[str, list[str]] = {
    "asset_class": [
        "asset_class", "asset class", "collateral type", "collateral_type",
        "security type", "type", "instrument type", "asset_type",
    ],
    "isin": ["isin", "cusip", "identifier", "security id", "sec_id", "isin/cusip"],
    "currency": ["currency", "ccy", "curr", "denomination"],
    "rating_floor": [
        "rating_floor", "rating floor", "minimum rating", "min rating",
        "min_rating", "rating minimum", "credit rating", "rating",
    ],
    "max_maturity_years": [
        "max_maturity_years", "max maturity", "maximum maturity",
        "maturity (years)", "maturity years", "maturity limit",
        "max tenor", "tenor limit",
    ],
    "haircut_pct": [
        "haircut_pct", "haircut", "haircut (%)", "hc", "hc (%)",
        "haircut percent", "haircut %", "margin %", "margin rate",
        "discount rate", "margin",
    ],
    "concentration_limit_pct": [
        "concentration_limit_pct", "concentration limit", "concentration (%)",
        "conc limit", "conc. limit", "max concentration", "concentration cap",
        "limit %", "portfolio limit",
    ],
    "eligible": [
        "eligible", "eligibility", "accepted", "allowed", "permitted",
        "is_eligible", "is eligible",
    ],
    "notes": ["notes", "comments", "remarks", "description", "note"],
}


def normalize_asset_class(raw: str) -> str:
    """Map a raw asset class label to a canonical AssetClass value."""
    key = raw.strip().lower()
    mapped = ASSET_CLASS_ALIASES.get(key)
    if mapped:
        return mapped.value
    # Prefix match
    for alias, cls in ASSET_CLASS_ALIASES.items():
        if key.startswith(alias) or alias.startswith(key):
            return cls.value
    return AssetClass.OTHER.value


def normalize_eligible(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        return raw.strip().lower() not in {"0", "false", "no", "n", "excluded", "ineligible", ""}
    return True
