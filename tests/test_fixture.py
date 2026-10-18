"""The committed CI fixture must clean under the same rules as a real extract."""

from pathlib import Path

from etl.clean.clean import (
    _apply_indicator_metadata,
    _read_wide_vaccination,
    _standardise_regions,
    _validate_rows,
    count_countries_below_threshold,
)

FIXTURE = Path(__file__).parent / "fixtures" / "vaccination_coverage.csv"


def test_fixture_matches_below_threshold_rule():
    long_df = _apply_indicator_metadata(_read_wide_vaccination(FIXTURE))
    long_df = _standardise_regions(long_df, {})
    clean, rejected = _validate_rows(long_df)

    assert rejected.empty
    assert {"dtp3", "measles_mcv1", "polio_pol3", "hepb3"} <= set(clean["indicator_code"])

    latest_year, below = count_countries_below_threshold(clean)
    assert latest_year == 2024
    assert below == 1
