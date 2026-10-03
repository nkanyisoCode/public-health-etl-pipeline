"""Streamlit dashboard — public health vaccination coverage."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from etl.config import get_engine  # noqa: E402

st.set_page_config(
    page_title="Vaccination Coverage Dashboard",
    page_icon="💉",
    layout="wide",
)


@st.cache_data(ttl=3600)
def load_trends() -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(
            "SELECT * FROM reporting.rpt_vaccination_trends ORDER BY region_name, year",
            conn,
        )


@st.cache_data(ttl=3600)
def load_below_threshold() -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(
            "SELECT * FROM reporting.rpt_below_threshold ORDER BY dtp3_coverage_pct",
            conn,
        )


@st.cache_data(ttl=3600)
def load_comparison() -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(
            "SELECT * FROM reporting.rpt_regional_comparison ORDER BY dtp3_coverage_pct DESC",
            conn,
        )


st.title("Public Health Vaccination Coverage Dashboard")
st.caption(
    "Data: OWID / WHO-UNICEF · Childhood vaccination coverage · "
    "Updated weekly via Airflow"
)

try:
    trends_df = load_trends()
    below_df = load_below_threshold()
    comparison_df = load_comparison()

    # --- Top metrics ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Countries Tracked", len(comparison_df))
    c2.metric("Below WHO 80% DTP3 Target", len(below_df))
    c3.metric("Latest Data Year", int(trends_df["year"].max()))

    st.divider()

    # --- Trend chart ---
    st.subheader("DTP3 Vaccination Coverage Trends")
    default_countries = [
        c for c in ["South Africa", "Nigeria", "Kenya", "India", "Brazil"]
        if c in trends_df["region_name"].values
    ]
    selected = st.multiselect(
        "Select countries to compare",
        options=sorted(trends_df["region_name"].unique()),
        default=default_countries,
    )
    if selected:
        fig = px.line(
            trends_df[trends_df["region_name"].isin(selected)],
            x="year",
            y="dtp3_coverage_pct",
            color="region_name",
            title="DTP3 Coverage (%) Over Time",
            labels={
                "dtp3_coverage_pct": "DTP3 Coverage (%)",
                "year": "Year",
                "region_name": "Country",
            },
        )
        fig.add_hline(
            y=80,
            line_dash="dash",
            line_color="red",
            annotation_text="WHO 80% target",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Below-threshold bar chart ---
    st.subheader(
        f"Countries Below WHO 80% DTP3 Target — {int(below_df['year'].iloc[0])} "
        f"({len(below_df)} countries)"
    )
    fig2 = px.bar(
        below_df.head(30),
        x="dtp3_coverage_pct",
        y="region_name",
        orientation="h",
        color="dtp3_coverage_pct",
        color_continuous_scale="RdYlGn",
        title="Lowest DTP3 Coverage Countries (latest year, bottom 30)",
        labels={
            "dtp3_coverage_pct": "DTP3 Coverage (%)",
            "region_name": "Country",
        },
    )
    fig2.add_vline(x=80, line_dash="dash", line_color="red")
    fig2.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig2, use_container_width=True)

    with st.expander("Show full below-threshold table"):
        st.dataframe(below_df, use_container_width=True)

    st.divider()

    # --- Regional comparison table ---
    st.subheader("All Countries — Latest Year Comparison")
    band_filter = st.selectbox(
        "Filter by coverage band",
        ["All", "At or above WHO target", "Moderate coverage", "Low coverage"],
    )
    filtered_comp = (
        comparison_df
        if band_filter == "All"
        else comparison_df[comparison_df["coverage_band"] == band_filter]
    )
    st.dataframe(filtered_comp, use_container_width=True)

except Exception as exc:
    st.error(
        f"Cannot connect to the database. Make sure PostgreSQL is running.\n\n`{exc}`"
    )
    st.info("Fix: `docker compose up -d postgres` — then reload this page.")
