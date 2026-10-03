"""Unit tests for etl.clean.clean — pure-function coverage (no DB / network)."""

import pandas as pd
import pytest

from etl.clean.clean import (
    _apply_indicator_metadata,
    _region_type,
    _standardise_regions,
    _validate_rows,
)
from etl.config import INDICATOR_COLUMNS


# ---------------------------------------------------------------------------
# _region_type
# ---------------------------------------------------------------------------


class TestRegionType:
    def test_three_letter_iso_is_country(self):
        assert _region_type("ZAF") == "country"
        assert _region_type("KEN") == "country"
        assert _region_type("USA") == "country"

    def test_owid_prefix_is_aggregate(self):
        assert _region_type("OWID_AFR") == "aggregate"
        assert _region_type("OWID_WRL") == "aggregate"

    def test_none_is_unknown(self):
        assert _region_type(None) == "unknown"

    def test_empty_string_is_unknown(self):
        assert _region_type("") == "unknown"

    def test_short_non_iso_code_is_other(self):
        assert _region_type("EU") == "other"


# ---------------------------------------------------------------------------
# _validate_rows
# ---------------------------------------------------------------------------


class TestValidateRows:
    def _row(self, year=2020, region_name="Testland", value=75.0, iso_code="TST"):
        return {
            "year": year,
            "region_name": region_name,
            "value": value,
            "iso_code": iso_code,
            "indicator_code": "dtp3",
        }

    def test_valid_row_goes_to_clean(self):
        df = pd.DataFrame([self._row()])
        clean, rejected = _validate_rows(df)
        assert len(clean) == 1
        assert len(rejected) == 0

    def test_year_too_old_is_rejected(self):
        df = pd.DataFrame([self._row(year=1900)])
        _, rejected = _validate_rows(df)
        assert len(rejected) == 1
        assert "invalid_year" in rejected.iloc[0]["reject_reason"]

    def test_null_year_is_rejected(self):
        df = pd.DataFrame([self._row(year=None)])
        _, rejected = _validate_rows(df)
        assert len(rejected) == 1
        assert "invalid_year" in rejected.iloc[0]["reject_reason"]

    def test_missing_region_name_is_rejected(self):
        df = pd.DataFrame([self._row(region_name=None)])
        _, rejected = _validate_rows(df)
        assert len(rejected) == 1
        assert "missing_region" in rejected.iloc[0]["reject_reason"]

    def test_blank_region_name_is_rejected(self):
        df = pd.DataFrame([self._row(region_name="   ")])
        _, rejected = _validate_rows(df)
        assert len(rejected) == 1
        assert "missing_region" in rejected.iloc[0]["reject_reason"]

    def test_value_above_100_is_rejected(self):
        df = pd.DataFrame([self._row(value=101.0)])
        _, rejected = _validate_rows(df)
        assert len(rejected) == 1
        assert "value_out_of_range" in rejected.iloc[0]["reject_reason"]

    def test_value_below_0_is_rejected(self):
        df = pd.DataFrame([self._row(value=-0.5)])
        _, rejected = _validate_rows(df)
        assert len(rejected) == 1
        assert "value_out_of_range" in rejected.iloc[0]["reject_reason"]

    def test_null_value_is_allowed(self):
        """Null values are flagged is_missing later, not rejected here."""
        df = pd.DataFrame([self._row(value=None)])
        clean, rejected = _validate_rows(df)
        assert len(clean) == 1
        assert len(rejected) == 0

    def test_boundary_values_are_valid(self):
        for v in (0.0, 100.0):
            df = pd.DataFrame([self._row(value=v)])
            clean, rejected = _validate_rows(df)
            assert len(clean) == 1, f"value={v} should be valid"
            assert len(rejected) == 0

    def test_multiple_reasons_combined(self):
        df = pd.DataFrame([self._row(year=1900, region_name=None)])
        _, rejected = _validate_rows(df)
        reason = rejected.iloc[0]["reject_reason"]
        assert "invalid_year" in reason
        assert "missing_region" in reason


# ---------------------------------------------------------------------------
# _standardise_regions
# ---------------------------------------------------------------------------


class TestStandardiseRegions:
    def _df(self, region_name="South Africa", iso_code="ZAF", value=80.0):
        return pd.DataFrame([{
            "region_name": region_name,
            "iso_code": iso_code,
            "value": value,
        }])

    def test_strips_whitespace_from_region_name(self):
        result = _standardise_regions(self._df(region_name="  South Africa  "), {})
        assert result.iloc[0]["region_name"] == "South Africa"

    def test_region_type_country_for_three_letter_iso(self):
        result = _standardise_regions(self._df(), {})
        assert result.iloc[0]["region_type"] == "country"

    def test_region_key_is_iso_when_present(self):
        result = _standardise_regions(self._df(), {})
        assert result.iloc[0]["region_key"] == "ZAF"

    def test_region_key_falls_back_to_slug_when_no_iso(self):
        result = _standardise_regions(self._df(iso_code=None), {})
        assert result.iloc[0]["region_key"] == "south_africa"

    def test_alias_lookup_fills_missing_iso(self):
        df = self._df(iso_code=None, region_name="DR Congo")
        result = _standardise_regions(df, {"DR Congo": "COD"})
        assert result.iloc[0]["iso_code"] == "COD"

    def test_nan_string_iso_treated_as_missing(self):
        result = _standardise_regions(self._df(iso_code="nan"), {})
        # "nan" must be normalised away
        val = result.iloc[0]["iso_code"]
        assert val is None or pd.isna(val)

    def test_does_not_mutate_original_dataframe(self):
        df = self._df()
        original_iso = df.iloc[0]["iso_code"]
        _standardise_regions(df, {})
        assert df.iloc[0]["iso_code"] == original_iso


# ---------------------------------------------------------------------------
# _apply_indicator_metadata
# ---------------------------------------------------------------------------


class TestApplyIndicatorMetadata:
    def _df_for(self, source_col: str):
        return pd.DataFrame([{
            "region_name": "Kenya",
            "iso_code": "KEN",
            "year": 2020,
            "indicator_source_col": source_col,
            "value": 72.0,
        }])

    def test_known_indicator_enriched_with_code_and_name(self):
        raw_col = next(iter(INDICATOR_COLUMNS))
        result = _apply_indicator_metadata(self._df_for(raw_col))
        assert len(result) == 1
        assert "indicator_code" in result.columns
        assert "indicator_name" in result.columns
        assert "indicator_category" in result.columns
        assert "indicator_unit" in result.columns

    def test_all_configured_indicators_map_correctly(self):
        for raw_col, (code, name, category, unit) in INDICATOR_COLUMNS.items():
            result = _apply_indicator_metadata(self._df_for(raw_col))
            assert result.iloc[0]["indicator_code"] == code
            assert result.iloc[0]["indicator_name"] == name

    def test_unknown_indicator_is_dropped(self):
        result = _apply_indicator_metadata(self._df_for("No Such Indicator XYZ"))
        assert len(result) == 0
