#!/usr/bin/env bash
# Initialize PostgreSQL schemas and staging tables.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

PGUSER="${POSTGRES_USER:-ph_user}"
PGDB="${POSTGRES_DB:-public_health_warehouse}"
export PGPASSWORD="${POSTGRES_PASSWORD:-ph_pass}"

echo "Initializing database schemas and staging tables..."
docker exec -i public_health_postgres psql -U "$PGUSER" -d postgres < "$SCRIPT_DIR/init_db.sql"
echo "Database ready."
