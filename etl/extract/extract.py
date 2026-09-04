"""Download OWID public health CSVs into dated raw snapshots."""

import shutil
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from etl.config import (
    HTTP_USER_AGENT,
    LANDING_DIR,
    OWID_DATASETS,
    RAW_DATA_DIR,
    snapshot_dir,
)
from etl.logger import get_logger

log = get_logger(__name__)


def _download(url: str, dest: Path) -> int:
    """Download a CSV from OWID. Returns row count."""
    response = requests.get(url, headers={"User-Agent": HTTP_USER_AGENT}, timeout=120)
    response.raise_for_status()
    dest.write_bytes(response.content)

    df = pd.read_csv(dest)
    return len(df)


def _latest_prior_snapshot(before: date) -> Path | None:
    """Find the most recent raw snapshot before the given date."""
    if not RAW_DATA_DIR.exists():
        return None

    candidates = []
    for path in RAW_DATA_DIR.iterdir():
        if not path.is_dir():
            continue
        try:
            snap_date = date.fromisoformat(path.name)
        except ValueError:
            continue
        if snap_date < before:
            candidates.append((snap_date, path))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def extract(for_date: date | None = None, use_cache: bool = False) -> dict[str, int]:
    """
    Download OWID datasets into data/raw/{date}/ and copy to landing/.
    Returns row counts per file.
    """
    snap = snapshot_dir(for_date)
    LANDING_DIR.mkdir(parents=True, exist_ok=True)
    counts = {}

    for key, meta in OWID_DATASETS.items():
        dest = snap / meta["filename"]
        landing = LANDING_DIR / meta["filename"]

        if use_cache and dest.exists():
            log.info("Cache hit — using existing snapshot for %s", key)
            shutil.copy2(dest, landing)
        else:
            log.info("Downloading %s from OWID...", key)
            row_count = _download(meta["url"], dest)
            shutil.copy2(dest, landing)
            counts[key] = row_count
            log.info("Downloaded %s: %d rows", key, row_count)
            continue

        counts[key] = sum(1 for _ in open(dest)) - 1

    prior = _latest_prior_snapshot(snap.name and date.fromisoformat(snap.name) or date.today())
    if prior:
        log.info("Prior snapshot available for revision detection: %s", prior.name)

    return counts


if __name__ == "__main__":
    result = extract()
    for name, count in result.items():
        log.info("%s: %d rows", name, count)
