"""Generate SVG charts used in the README from reporting views."""

import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl.config import get_engine  # noqa: E402

SCREENSHOTS_DIR = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
HIGHLIGHT_COUNTRIES = [
    "South Africa", "Nigeria", "Kenya", "India", "Brazil", "World",
]


def generate_trends_chart(engine) -> None:
    with engine.connect() as conn:
        df = pd.read_sql(
            """
            SELECT region_name, year, dtp3_coverage_pct
            FROM reporting.rpt_vaccination_trends
            WHERE region_name = ANY(%(countries)s)
            ORDER BY region_name, year
            """,
            conn,
            params={"countries": HIGHLIGHT_COUNTRIES},
        )

    fig, ax = plt.subplots(figsize=(10, 5))
    for country, grp in df.groupby("region_name"):
        ax.plot(
            grp["year"],
            grp["dtp3_coverage_pct"],
            marker="o",
            markersize=2,
            label=country,
        )
    ax.axhline(y=80, color="red", linestyle="--", linewidth=1, label="WHO 80% target")
    ax.set_xlabel("Year")
    ax.set_ylabel("DTP3 Coverage (%)")
    ax.set_title("DTP3 Vaccination Coverage Trends (Selected Countries)")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    out = SCREENSHOTS_DIR / "dtp3_trends.svg"
    fig.savefig(out, format="svg")
    plt.close(fig)
    print(f"Saved: {out}")


def generate_comparison_chart(engine) -> None:
    with engine.connect() as conn:
        df = pd.read_sql(
            """
            SELECT region_name, dtp3_coverage_pct
            FROM reporting.rpt_regional_comparison
            ORDER BY dtp3_coverage_pct DESC
            LIMIT 30
            """,
            conn,
        )

    colors = ["#d73027" if v < 80 else "#1a9850" for v in df["dtp3_coverage_pct"]]
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(df["region_name"], df["dtp3_coverage_pct"], color=colors)
    ax.axvline(x=80, color="red", linestyle="--", linewidth=1, label="WHO 80% target")
    ax.set_xlabel("DTP3 Coverage (%)")
    ax.set_title("Regional DTP3 Coverage — Latest Year (Top 30 Countries)")
    ax.legend()
    ax.set_xlim(0, 105)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()

    out = SCREENSHOTS_DIR / "regional_comparison.svg"
    fig.savefig(out, format="svg")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    generate_trends_chart(engine)
    generate_comparison_chart(engine)
    print("README charts generated successfully.")
