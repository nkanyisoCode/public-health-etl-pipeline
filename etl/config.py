"""Shared configuration for the public health ETL pipeline."""

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
LANDING_DIR = PROJECT_ROOT / "data" / "landing"
CLEANED_DIR = PROJECT_ROOT / "data" / "cleaned"
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"

# OWID datasets — WHO/UNICEF childhood vaccination coverage
# DTP3 is extracted from the wide vaccination_coverage file via INDICATOR_COLUMNS; no separate download needed.
OWID_DATASETS = {
    "vaccination_coverage": {
        "url": (
            "https://ourworldindata.org/grapher/vaccination-coverage-who-unicef.csv"
            "?v=1&csvType=full&useColumnShortNames=false"
            "&antigen=comparison&metric=coverage"
        ),
        "filename": "vaccination_coverage.csv",
    },
}

# Indicators extracted from the wide vaccination coverage file
INDICATOR_COLUMNS = {
    "Measles, first dose (MCV1)": ("measles_mcv1", "Measles (MCV1)", "vaccination", "%"),
    "Diphtheria/tetanus/pertussis (DTP3)": ("dtp3", "DTP3", "vaccination", "%"),
    "Polio (Pol3)": ("polio_pol3", "Polio (Pol3)", "vaccination", "%"),
    "Hepatitis B (HepB3)": ("hepb3", "Hepatitis B (HepB3)", "vaccination", "%"),
}

WHO_THRESHOLD_PCT = 80.0
HTTP_USER_AGENT = "Public-Health-ETL/1.0 (portfolio project)"


def snapshot_dir(for_date: date | None = None) -> Path:
    """Return dated raw snapshot directory (creates if needed)."""
    day = for_date or date.today()
    path = RAW_DATA_DIR / day.isoformat()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_url() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5433")
    db = os.getenv("POSTGRES_DB", "public_health_warehouse")
    user = os.getenv("POSTGRES_USER", "ph_user")
    password = os.getenv("POSTGRES_PASSWORD", "ph_pass")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def get_engine():
    return create_engine(get_db_url())
