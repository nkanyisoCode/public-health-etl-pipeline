"""Load cleaned CSV data into PostgreSQL staging tables."""

import json
from datetime import datetime, timezone
UTC = timezone.utc

import pandas as pd
from sqlalchemy import text

from etl.config import CLEANED_DIR, get_engine
from etl.logger import get_logger

log = get_logger(__name__)

TABLE_MAP = {
    "health_indicators_clean.csv": "staging.stg_health_indicators",
    "regions_clean.csv": "staging.stg_regions",
    "rejected_rows.csv": "staging.stg_rejected_rows",
    "data_revisions.csv": "staging.stg_data_revisions",
}


def _write_quality_log(conn, table: str, row_count: int) -> None:
    """Record a load event in staging.data_quality_log."""
    conn.execute(
        text(
            """
            INSERT INTO staging.data_quality_log
                (table_name, check_name, check_result, details)
            VALUES
                (:table_name, :check_name, :check_result, :details)
            """
        ),
        {
            "table_name": table,
            "check_name": "row_count",
            "check_result": "passed",
            "details": json.dumps(
                {"rows_loaded": row_count, "loaded_at": datetime.now(UTC).isoformat()}
            ),
        },
    )


def load(mode: str = "replace") -> dict[str, int]:
    """Load cleaned CSVs into staging. mode='replace' truncates first."""
    engine = get_engine()
    counts: dict[str, int] = {}

    with engine.begin() as conn:
        for filename, table in TABLE_MAP.items():
            path = CLEANED_DIR / filename
            if not path.exists() or path.stat().st_size == 0:
                log.warning("Skipping missing/empty file: %s", filename)
                continue

            try:
                df = pd.read_csv(path)
            except pd.errors.EmptyDataError:
                log.warning("Skipping empty file: %s", filename)
                continue

            if df.empty:
                log.warning("Skipping empty DataFrame for file: %s", filename)
                continue

            for col in ("is_missing", "is_revised", "is_estimated"):
                if col in df.columns:
                    df[col] = df[col].map(
                        {True: True, False: False, "True": True, "False": False}
                    ).astype(bool)

            if mode == "replace":
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))

            schema, table_name = table.split(".")
            df.to_sql(
                table_name,
                conn,
                schema=schema,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=5000,
            )
            counts[table] = len(df)
            log.info("Loaded %d rows into %s", len(df), table)
            _write_quality_log(conn, table, len(df))

        if counts:
            conn.execute(
                text(
                    """
                    INSERT INTO staging.data_quality_log
                        (table_name, check_name, check_result, details)
                    VALUES
                        (:table_name, :check_name, :check_result, :details)
                    """
                ),
                {
                    "table_name": "pipeline",
                    "check_name": "pipeline_run",
                    "check_result": "passed",
                    "details": json.dumps(
                        {
                            "tables_loaded": len(counts),
                            "total_rows": sum(counts.values()),
                            "run_at": datetime.now(UTC).isoformat(),
                        }
                    ),
                },
            )
            log.info(
                "Pipeline run logged: %d tables, %d total rows",
                len(counts),
                sum(counts.values()),
            )

    return counts


if __name__ == "__main__":
    load()
