#!/usr/bin/env bash
# Run the full public health ETL pipeline locally (without Airflow).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

export PYTHONPATH="$PROJECT_DIR"

PYTHON="${PROJECT_DIR}/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    PYTHON="python3"
fi

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

if ! docker ps --format '{{.Names}}' | grep -q '^public_health_postgres$'; then
    echo "Postgres container not running. Start it with: docker compose up -d postgres"
    exit 1
fi

if ! docker exec public_health_postgres psql -U ph_user -d public_health_warehouse -c \
    "SELECT 1 FROM information_schema.tables WHERE table_schema='staging' AND table_name='stg_health_indicators';" \
    | grep -q 1; then
    echo "Staging tables not found — initializing database..."
    "$SCRIPT_DIR/init_db.sh"
fi

echo "=== Step 1: Extract (download OWID data) ==="
"$PYTHON" -m etl.extract.extract

echo "=== Step 2: Clean ==="
"$PYTHON" -m etl.clean.clean

echo "=== Step 3: Load to staging ==="
"$PYTHON" -m etl.load.load

echo "=== Step 4: dbt run ==="
cd dbt
"${PROJECT_DIR}/.venv/bin/dbt" deps --profiles-dir .
"${PROJECT_DIR}/.venv/bin/dbt" run --profiles-dir .
"${PROJECT_DIR}/.venv/bin/dbt" test --profiles-dir .
cd "$PROJECT_DIR"

echo "=== Pipeline complete ==="
