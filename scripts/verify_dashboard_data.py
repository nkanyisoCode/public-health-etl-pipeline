"""Verify that all reporting views have data before launching the dashboard."""

import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.config import get_engine  # noqa: E402

VIEWS = {
    "trends": "reporting.rpt_vaccination_trends",
    "comparison": "reporting.rpt_regional_comparison",
    "below_threshold": "reporting.rpt_below_threshold",
}


def verify() -> None:
    engine = get_engine()
    all_ok = True

    with engine.connect() as conn:
        for name, view in VIEWS.items():
            count = conn.execute(text(f"SELECT COUNT(*) FROM {view}")).scalar()
            status = "OK" if count and count > 0 else "EMPTY"
            if status == "EMPTY":
                all_ok = False
            print(f"  {name}: {count} rows [{status}]")

    if all_ok:
        print("Dashboard data layer verified.")
    else:
        print("\nERROR: one or more views are empty. Run the full pipeline first:")
        print("  ./scripts/run_pipeline.sh")
        sys.exit(1)


if __name__ == "__main__":
    verify()
