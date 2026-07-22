"""Tests for the deterministic post-extraction validation pass (_post_validate)."""

import pytest

from collateral_schedule.llm_parser import validate_llm_entries


# --------------------------------------------------------------------------- #
# Rule 1: margin % → haircut auto-conversion
# --------------------------------------------------------------------------- #
class TestMarginToHaircutConversion:
    def test_large_haircut_on_eligible_entry_is_converted(self):
        entries = [{"asset_class": "GOVT", "haircut_pct": 99.0, "eligible": True}]
        result = validate_llm_entries(entries)
        assert result[0]["haircut_pct"] == pytest.approx(1.0)
        assert "auto-corrected" in result[0]["notes"]
        assert "99" in result[0]["notes"]

    def test_conversion_preserves_existing_notes(self):
        entries = [{"asset_class": "CORP", "haircut_pct": 95.0, "eligible": True, "notes": "prior note"}]
        result = validate_llm_entries(entries)
        assert "prior note" in result[0]["notes"]
        assert "auto-corrected" in result[0]["notes"]

    def test_borderline_50_is_not_converted(self):
        # Exactly 50 should not be touched — legitimate haircut (e.g. HY equity)
        entries = [{"asset_class": "EQUITY", "haircut_pct": 50.0, "eligible": True}]
        result = validate_llm_entries(entries)
        assert result[0]["haircut_pct"] == 50.0
        assert "auto-corrected" not in (result[0].get("notes") or "")

    def test_ineligible_entry_with_high_haircut_is_not_converted(self):
        # A 100% haircut on an ineligible entry is the correct representation
        entries = [{"asset_class": "EQUITY", "haircut_pct": 100.0, "eligible": False}]
        result = validate_llm_entries(entries)
        assert result[0]["haircut_pct"] == 100.0

    def test_normal_haircut_unchanged(self):
        entries = [{"asset_class": "GOVT", "haircut_pct": 2.5, "eligible": True}]
        result = validate_llm_entries(entries)
        assert result[0]["haircut_pct"] == 2.5
        assert "auto-corrected" not in (result[0].get("notes") or "")

    def test_missing_haircut_passes_through(self):
        entries = [{"asset_class": "CASH", "eligible": True}]
        result = validate_llm_entries(entries)
        assert "haircut_pct" not in result[0]


# --------------------------------------------------------------------------- #
# Rule 2: impossible maturity years
# --------------------------------------------------------------------------- #
class TestImpossibleMaturity:
    def test_calendar_year_maturity_is_cleared(self):
        # Model emitted 2030 (a calendar year) instead of e.g. 5 (years)
        entries = [{"asset_class": "GOVT", "max_maturity_years": 2030.0}]
        result = validate_llm_entries(entries)
        assert "max_maturity_years" not in result[0]
        assert "auto-corrected" in result[0]["notes"]
        assert "2030" in result[0]["notes"]

    def test_exactly_100_is_cleared(self):
        entries = [{"asset_class": "GOVT", "max_maturity_years": 100.1}]
        result = validate_llm_entries(entries)
        assert "max_maturity_years" not in result[0]

    def test_plausible_30_year_bond_is_kept(self):
        entries = [{"asset_class": "GOVT", "max_maturity_years": 30.0}]
        result = validate_llm_entries(entries)
        assert result[0]["max_maturity_years"] == 30.0

    def test_existing_notes_preserved_on_maturity_correction(self):
        entries = [{"asset_class": "CORP", "max_maturity_years": 2028.0, "notes": "USD only"}]
        result = validate_llm_entries(entries)
        assert "USD only" in result[0]["notes"]
        assert "auto-corrected" in result[0]["notes"]


# --------------------------------------------------------------------------- #
# Rule 3: second-chance OTHER resolution
# --------------------------------------------------------------------------- #
class TestSecondChanceAssetClass:
    def test_other_with_govt_label_in_notes_is_resolved(self):
        entries = [{"asset_class": "OTHER", "notes": "US Treasury Bills and Notes"}]
        result = validate_llm_entries(entries)
        assert result[0]["asset_class"] == "GOVT"

    def test_other_with_corporate_label_is_resolved(self):
        entries = [{"asset_class": "OTHER", "notes": "Investment Grade Corporate Bonds."}]
        result = validate_llm_entries(entries)
        assert result[0]["asset_class"] == "CORP"

    def test_other_with_truly_unknown_label_stays_other(self):
        entries = [{"asset_class": "OTHER", "notes": "Antique Silverware."}]
        result = validate_llm_entries(entries)
        assert result[0]["asset_class"] == "OTHER"

    def test_other_without_notes_stays_other(self):
        entries = [{"asset_class": "OTHER"}]
        result = validate_llm_entries(entries)
        assert result[0]["asset_class"] == "OTHER"

    def test_non_other_class_is_not_re_resolved(self):
        entries = [{"asset_class": "CORP", "notes": "US Treasury Bills"}]
        result = validate_llm_entries(entries)
        # CORP should not be changed even if notes mention govt
        assert result[0]["asset_class"] == "CORP"


# --------------------------------------------------------------------------- #
# Rule 4: duplicate key de-duplication (keep lowest haircut)
# --------------------------------------------------------------------------- #
class TestDuplicateDeduplication:
    def test_duplicate_keeps_lowest_haircut(self):
        entries = [
            {"asset_class": "GOVT", "max_maturity_years": 5.0, "rating_floor": None, "isin": None, "haircut_pct": 3.0},
            {"asset_class": "GOVT", "max_maturity_years": 5.0, "rating_floor": None, "isin": None, "haircut_pct": 2.0},
        ]
        result = validate_llm_entries(entries)
        assert len(result) == 1
        assert result[0]["haircut_pct"] == 2.0

    def test_different_rating_floors_not_deduplicated(self):
        entries = [
            {"asset_class": "CORP", "max_maturity_years": 5.0, "rating_floor": "AAA", "isin": None, "haircut_pct": 2.0},
            {"asset_class": "CORP", "max_maturity_years": 5.0, "rating_floor": "BBB", "isin": None, "haircut_pct": 5.0},
        ]
        result = validate_llm_entries(entries)
        assert len(result) == 2

    def test_different_maturities_not_deduplicated(self):
        entries = [
            {"asset_class": "GOVT", "max_maturity_years": 1.0, "rating_floor": None, "isin": None, "haircut_pct": 1.0},
            {"asset_class": "GOVT", "max_maturity_years": 5.0, "rating_floor": None, "isin": None, "haircut_pct": 2.0},
        ]
        result = validate_llm_entries(entries)
        assert len(result) == 2

    def test_duplicate_without_haircut_keeps_first(self):
        entries = [
            {"asset_class": "CASH", "max_maturity_years": None, "rating_floor": None, "isin": None},
            {"asset_class": "CASH", "max_maturity_years": None, "rating_floor": None, "isin": None},
        ]
        result = validate_llm_entries(entries)
        assert len(result) == 1


# --------------------------------------------------------------------------- #
# Combined / ordering
# --------------------------------------------------------------------------- #
class TestCombinedCorrections:
    def test_margin_conversion_then_duplicate_dedup(self):
        # Both entries are margin % for the same key; after conversion they
        # should both become valid haircuts and then be deduplicated.
        entries = [
            {"asset_class": "GOVT", "haircut_pct": 99.0, "eligible": True,
             "max_maturity_years": 5.0, "rating_floor": None, "isin": None},
            {"asset_class": "GOVT", "haircut_pct": 98.0, "eligible": True,
             "max_maturity_years": 5.0, "rating_floor": None, "isin": None},
        ]
        result = validate_llm_entries(entries)
        # Both converted: 99→1, 98→2; lower haircut (1%) wins
        assert len(result) == 1
        assert result[0]["haircut_pct"] == pytest.approx(1.0)

    def test_empty_list_returns_empty(self):
        assert validate_llm_entries([]) == []

    def test_source_row_not_present_before_validation(self):
        # validate_llm_entries should not assign source_row — that's done in
        # _entries_from_schedule after this call.
        entries = [{"asset_class": "GOVT", "haircut_pct": 2.0}]
        result = validate_llm_entries(entries)
        assert "source_row" not in result[0]
