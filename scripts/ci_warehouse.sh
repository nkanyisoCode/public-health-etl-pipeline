#!/usr/bin/env bash
# Load the committed fixture and build the warehouse.
# GitHub Actions publishes Postgres on port 5432. Local Compose uses 5433:
#   POSTGRES_PORT=5433 ./scripts/ci_warehouse.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_DB="${POSTGRES_DB:-public_health_warehouse}"
export POSTGRES_USER="${POSTGRES_USER:-ph_user}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-ph_pass}"
export PGPASSWORD="$POSTGRES_PASSWORD"
export PYTHONPATH="$PROJECT_DIR"

echo "=== Init staging tables ==="
# Skip the Airflow database bootstrap. CI connects straight to the warehouse.
grep -v -E '^(CREATE DATABASE|\\c )' "$SCRIPT_DIR/init_db.sql" \
    | psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" -v ON_ERROR_STOP=1

echo "=== Clean fixture ==="
mkdir -p data/landing
cp tests/fixtures/vaccination_coverage.csv data/landing/vaccination_coverage.csv
python -m etl.clean.clean

echo "=== Load staging ==="
python -m etl.load.load

echo "=== dbt run and test ==="
cd dbt
dbt deps --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .
cd "$PROJECT_DIR"

echo "=== Check reporting view ==="
below="$(psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" -tA -c "SELECT count(*) FROM reporting.rpt_below_threshold;")"
below="${below//$'\r'/}"
if [ "$below" != "1" ]; then
    echo "reporting.rpt_below_threshold expected 1 country, got: ${below}"
    exit 1
fi

echo "Warehouse CI passed."
