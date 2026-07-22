"""
collateral_schedule — standalone counterparty collateral schedule library.

Ingests eligible collateral schedules (CSV, XLSX, PDF) per counterparty and
margin type, normalises them to a unified data model, and persists them in a
local SQLite database.  Designed to be used independently of any parent
project; the decision_intelligence API is just one consumer.
"""

from .database import CollateralDatabase
from .llm_parser import LLMCollateralSchedule, parse_pdf_with_llm, validate_llm_entries
from .models import AssetClass, MarginType, normalize_rating, validate_isin
from .parser import parse_schedule

__all__ = [
    "CollateralDatabase",
    "AssetClass",
    "MarginType",
    "normalize_rating",
    "validate_isin",
    "parse_schedule",
    "parse_pdf_with_llm",
    "validate_llm_entries",
    "LLMCollateralSchedule",
]
