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


# Moody's long-form → S&P-style canonical mapping
_MOODYS_LONG: dict[str, str] = {
    "aaa": "AAA", "aa1": "AA+", "aa2": "AA", "aa3": "AA-",
    "a1": "A+", "a2": "A", "a3": "A-",
    "baa1": "BBB+", "baa2": "BBB", "baa3": "BBB-",
    "ba1": "BB+", "ba2": "BB", "ba3": "BB-",
    "b1": "B+", "b2": "B", "b3": "B-",
    "caa1": "CCC+", "caa2": "CCC", "caa3": "CCC-",
    "ca": "CC", "c": "D",
    # Watchlist suffixes that appear in source data
    "aaa (stable)": "AAA", "aa+ (stable)": "AA+",
}

# S&P / Fitch canonical ratings (returned as-is after upper-casing)
_SP_CANONICAL: frozenset[str] = frozenset({
    "AAA", "AA+", "AA", "AA-",
    "A+", "A", "A-",
    "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-",
    "B+", "B", "B-",
    "CCC+", "CCC", "CCC-",
    "CC", "C", "D", "NR", "WR",
})

# Common shorthand / aliases not in Moody's long form
_RATING_ALIASES: dict[str, str] = {
    "investment grade": "BBB-",
    "ig": "BBB-",
    "non-investment grade": "BB+",
    "hy": "BB+",
    "high yield": "BB+",
    "speculative": "BB+",
    "not rated": "NR",
    "unrated": "NR",
    "withdrawn": "WR",
}


def normalize_rating(raw: str) -> str:
    """Map a free-text rating string to a canonical S&P-style rating.

    Handles S&P, Fitch (identical notation), Moody's long-form (e.g. ``Aaa``,
    ``Baa3``), and common aliases (``Investment Grade`` → ``BBB-``).  Unknown
    strings are returned upper-cased so they round-trip without data loss.
    """
    if not raw or not isinstance(raw, str):
        return "NR"
    key = raw.strip().lower()
    # Remove watch/outlook suffixes: "AA+ (stable)" → "aa+"
    for suffix in (" (stable)", " (negative)", " (positive)", " (developing)", " watch"):
        key = key.replace(suffix, "")
    key = key.strip()

    # Check Moody's long form
    if key in _MOODYS_LONG:
        return _MOODYS_LONG[key]
    # Check aliases
    if key in _RATING_ALIASES:
        return _RATING_ALIASES[key]
    # Check S&P / Fitch canonical (case-insensitive)
    upper = key.upper()
    if upper in _SP_CANONICAL:
        return upper
    # Unknown — return upper-cased original so it's legible
    return raw.strip().upper()


def validate_isin(isin: str) -> tuple[bool, str]:
    """Validate an ISIN using the ISO 6166 Luhn-mod-10 checksum.

    Returns ``(True, "")`` for a valid ISIN, or ``(False, reason)`` for an
    invalid one.  CUSIPs (9-char) are accepted and treated as valid identifiers
    even though they don't follow ISIN structure.
    """
    if not isin or not isinstance(isin, str):
        return False, "empty"
    raw = isin.strip().upper()

    # CUSIP: 9 alphanumeric characters — no ISIN checksum, accept as-is
    if len(raw) == 9 and raw.isalnum():
        return True, ""

    if len(raw) != 12:
        return False, f"wrong length ({len(raw)}, expected 12)"

    if not raw[:2].isalpha():
        return False, "first two characters must be alphabetic country code"

    if not raw[2:].isalnum():
        return False, "characters 3-12 must be alphanumeric"

    # Convert each character to digits: A=10, B=11, …, Z=35
    digits: list[int] = []
    for ch in raw:
        if ch.isdigit():
            digits.append(int(ch))
        else:
            val = ord(ch) - ord("A") + 10
            digits.extend(divmod(val, 10))

    # Luhn mod-10 over the expanded digit string
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d

    if total % 10 != 0:
        return False, "checksum failed"
    return True, ""


def normalize_eligible(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        return raw.strip().lower() not in {"0", "false", "no", "n", "excluded", "ineligible", ""}
    return True
