"""Clean and standardise OWID public health CSV data."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
UTC = timezone.utc
from pathlib import Path

import pandas as pd

from etl.config import (
    CLEANED_DIR,
    INDICATOR_COLUMNS,
    LANDING_DIR,
    RAW_DATA_DIR,
    REFERENCE_DIR,
    WHO_THRESHOLD_PCT,
)
from etl.logger import get_logger

log = get_logger(__name__)

VALUE_MIN = 0.0
VALUE_MAX = 100.0


def _load_region_aliases() -> dict[str, str]:
    """Map alternate region names to canonical ISO codes."""
    path = REFERENCE_DIR / "region_aliases.csv"
    if not path.exists():
        return {}
    aliases = pd.read_csv(path, dtype=str)
    return dict(zip(aliases["alias"].str.strip(), aliases["iso_code"].str.strip()))


def _region_type(iso_code: str | None) -> str:
    if not iso_code or pd.isna(iso_code):
        return "unknown"
    code = str(iso_code).strip()
    if code.startswith("OWID_"):
        return "aggregate"
    if len(code) == 3:
        return "country"
    return "other"


def _read_wide_vaccination(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={"Entity": "region_name", "Code": "iso_code", "Year": "year"})
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

    value_cols = [c for c in df.columns if c in INDICATOR_COLUMNS]
    long_df = df.melt(
        id_vars=["region_name", "iso_code", "year"],
        value_vars=value_cols,
        var_name="indicator_source_col",
        value_name="value",
    )
    long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")
    return long_df


def _apply_indicator_metadata(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        meta = INDICATOR_COLUMNS.get(row["indicator_source_col"])
        if not meta:
            continue
        indicator_code, indicator_name, category, unit = meta
        rows.append(
            {
                **row.to_dict(),
                "indicator_code": indicator_code,
                "indicator_name": indicator_name,
                "indicator_category": category,
                "indicator_unit": unit,
            }
        )
    return pd.DataFrame(rows)


def _standardise_regions(df: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    df = df.copy()
    df["region_name"] = df["region_name"].str.strip()
    df["iso_code"] = df["iso_code"].astype(str).str.strip().replace({"nan": None, "None": None})

    # Fill missing ISO from alias table (handles name drift edge cases)
    missing_code = df["iso_code"].isna() | (df["iso_code"] == "")
    df.loc[missing_code, "iso_code"] = df.loc[missing_code, "region_name"].map(aliases)

    df["region_type"] = df["iso_code"].apply(_region_type)
    df["region_key"] = df["iso_code"].fillna(df["region_name"].str.lower().str.replace(" ", "_"))
    return df


def _validate_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split valid rows from rejected rows with reasons."""
    records = []
    rejected = []

    for idx, row in df.iterrows():
        reasons = []
        if pd.isna(row["year"]) or row["year"] < 1980 or row["year"] > datetime.now().year + 1:
            reasons.append("invalid_year")
        if pd.isna(row["region_name"]) or not str(row["region_name"]).strip():
            reasons.append("missing_region")
        if pd.notna(row["value"]) and (row["value"] < VALUE_MIN or row["value"] > VALUE_MAX):
            reasons.append("value_out_of_range")

        if reasons:
            rejected.append(
                {
                    "source_row": int(idx),
                    "region_name": row.get("region_name"),
                    "iso_code": row.get("iso_code"),
                    "year": row.get("year"),
                    "indicator_code": row.get("indicator_code"),
                    "value": row.get("value"),
                    "reject_reason": "|".join(reasons),
                }
            )
        else:
            records.append(row)

    clean = pd.DataFrame(records)
    reject_df = pd.DataFrame(rejected)
    return clean, reject_df


def _detect_revisions(current: pd.DataFrame, prior_snapshot_dir: Path | None) -> pd.DataFrame:
    """Compare current landing file against prior raw snapshot."""
    if prior_snapshot_dir is None:
        return pd.DataFrame(
            columns=[
                "region_key",
                "year",
                "indicator_code",
                "old_value",
                "new_value",
                "prior_snapshot",
                "detected_at",
            ]
        )

    prior_path = prior_snapshot_dir / "vaccination_coverage.csv"
    if not prior_path.exists():
        return pd.DataFrame()

    prior_long = _apply_indicator_metadata(_read_wide_vaccination(prior_path))
    prior_long = _standardise_regions(prior_long, _load_region_aliases())

    keys = ["region_key", "year", "indicator_code"]
    cur = current.dropna(subset=["value"])[keys + ["value"]].copy()
    old = prior_long.dropna(subset=["value"])[keys + ["value"]].copy()

    merged = cur.merge(old, on=keys, how="inner", suffixes=("_new", "_old"))
    changed = merged[merged["value_new"] != merged["value_old"]].copy()

    if changed.empty:
        return pd.DataFrame()

    return pd.DataFrame(
        {
            "region_key": changed["region_key"],
            "year": changed["year"],
            "indicator_code": changed["indicator_code"],
            "old_value": changed["value_old"],
            "new_value": changed["value_new"],
            "prior_snapshot": prior_snapshot_dir.name,
            "detected_at": datetime.utcnow().isoformat(),
        }
    )


def _find_prior_snapshot() -> Path | None:
    if not RAW_DATA_DIR.exists():
        return None
    dirs = sorted(
        [p for p in RAW_DATA_DIR.iterdir() if p.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    )
    if len(dirs) < 2:
        return None
    return dirs[1]  # second-most-recent (most recent is today's download)


def clean() -> dict:
    """Clean landing CSVs and write to cleaned/. Returns quality stats."""
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    aliases = _load_region_aliases()

    src = LANDING_DIR / "vaccination_coverage.csv"
    if not src.exists():
        raise FileNotFoundError(
            f"Missing {src}. Run extract first: python -m etl.extract.extract"
        )
    log.info("Cleaning %s", src.name)

    long_df = _read_wide_vaccination(src)
    long_df = _apply_indicator_metadata(long_df)
    long_df = _standardise_regions(long_df, aliases)

    # Flag rows where value is null (common in lower-reporting countries)
    long_df["is_missing"] = long_df["value"].isna()

    clean_df, rejected_df = _validate_rows(long_df)

    revisions = _detect_revisions(long_df, _find_prior_snapshot())
    if not revisions.empty:
        clean_df = clean_df.merge(
            revisions[keys := ["region_key", "year", "indicator_code"]],
            on=keys,
            how="left",
            indicator=True,
        )
        clean_df["is_revised"] = clean_df["_merge"] == "both"
        clean_df = clean_df.drop(columns=["_merge"])
    else:
        clean_df["is_revised"] = False

    clean_df["is_estimated"] = clean_df["is_missing"] | clean_df["is_revised"]
    clean_df["loaded_at"] = datetime.utcnow().isoformat()

    # Region dimension extract (one row per region)
    regions = (
        clean_df[["region_key", "region_name", "iso_code", "region_type"]]
        .drop_duplicates(subset=["region_key"])
        .sort_values("region_name")
    )

    out_indicators = CLEANED_DIR / "health_indicators_clean.csv"
    out_regions = CLEANED_DIR / "regions_clean.csv"
    out_rejected = CLEANED_DIR / "rejected_rows.csv"
    out_revisions = CLEANED_DIR / "data_revisions.csv"

    export_cols = [
        "region_key",
        "region_name",
        "iso_code",
        "region_type",
        "year",
        "indicator_code",
        "indicator_name",
        "indicator_category",
        "indicator_unit",
        "value",
        "is_missing",
        "is_revised",
        "is_estimated",
        "loaded_at",
    ]
    clean_df[export_cols].to_csv(out_indicators, index=False)
    regions.to_csv(out_regions, index=False)
    rejected_df.to_csv(out_rejected, index=False)
    log.info(
        "Cleaned %d indicator rows | %d regions | %d rejected | %d revisions",
        len(clean_df),
        len(regions),
        len(rejected_df),
        len(revisions),
    )
    revision_export = revisions if not revisions.empty else pd.DataFrame(
        columns=[
            "region_key", "year", "indicator_code",
            "old_value", "new_value", "prior_snapshot", "detected_at",
        ]
    )
    revision_export.to_csv(out_revisions, index=False)

    countries = regions[regions["region_type"] == "country"]
    dtp3 = clean_df[clean_df["indicator_code"] == "dtp3"].dropna(subset=["value"])
    latest_year = int(dtp3["year"].max()) if not dtp3.empty else None
    below_threshold = 0
    if latest_year:
        latest = dtp3[dtp3["year"] == latest_year]
        below_threshold = int((latest["value"] < WHO_THRESHOLD_PCT).sum())

    stats = {
        "indicator_rows": len(clean_df),
        "region_count": len(regions),
        "country_count": len(countries),
        "null_values": int(clean_df["is_missing"].sum()),
        "rejected_rows": len(rejected_df),
        "revisions_detected": len(revisions),
        "latest_dtp3_year": latest_year,
        "countries_below_80pct_dtp3": below_threshold,
        "files_written": [str(out_indicators), str(out_regions)],
    }
    return stats


if __name__ == "__main__":
    result = clean()
    log.info("Quality stats:\n%s", json.dumps(result, indent=2))
