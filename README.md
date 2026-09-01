# Public Health ETL Pipeline

Real-world public health data pipeline using **Our World in Data (OWID)** vaccination statistics from WHO & UNICEF.

## Analytical Question

> **How has childhood DTP3 vaccination coverage changed across regions over the last 15 years, and which countries fall below the WHO 80% target?**

## Architecture

```
OWID CSV download (HTTPS)
        ↓
Raw landing zone (dated snapshots: data/raw/YYYY-MM-DD/)
        ↓
Extract & clean (pandas) — missing values, region standardisation, revision detection
        ↓
PostgreSQL staging tables
        ↓
Transform (dbt) → star schema warehouse + quality tests
        ↓
Orchestrated by Airflow (weekly schedule)
        ↓
Reporting (Streamlit + SQL views)
```

## Tech Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| Data source | OWID / WHO-UNICEF | Real public vaccination coverage CSVs |
| Cleaning | pandas | Validate, standardise, flag revisions |
| Storage | PostgreSQL | Staging + warehouse |
| Modelling | dbt | Star schema + data quality tests |
| Orchestration | Airflow | Scheduled pipeline refresh |
| Reporting | Streamlit | Trends and regional comparisons |

## Project Structure

```
public-health-etl-pipeline/
├── data/
│   ├── raw/              # dated OWID snapshots
│   ├── landing/          # current extract copy
│   ├── cleaned/          # pandas output
│   └── reference/        # region alias mappings
├── etl/                  # extract, clean, load
├── dbt/                  # star schema + reporting views
├── airflow/dags/         # weekly orchestration
├── reporting/streamlit/  # dashboard
├── docs/                 # data quality report
├── scripts/              # init_db, run_pipeline
└── docker-compose.yml    # Postgres + Airflow (port 5433 / 8081)
```

## Quick Start (Clone & Run)

Follow these steps from scratch if you have never run this project before.

### 1. Clone and install

```bash
git clone https://github.com/nkanyisoCode/public-health-etl-pipeline.git
cd public-health-etl-pipeline

python3 -m venv .venv
source .venv/bin/activate        # You must run this every new terminal session
cp .env.example .env
pip install -r requirements.txt          # ETL + dbt + dashboard
```

> **Important:** Always activate the virtual environment before running Python commands.
> Your prompt should show `(.venv)`. Use `python` (from the venv), **not** system `python3`.
>
> ```bash
> which python
> # Should show: .../public-health-etl-pipeline/.venv/bin/python
> ```

### 2. Start PostgreSQL

```bash
docker compose up -d postgres
chmod +x scripts/*.sh
./scripts/init_db.sh
```

Confirm Postgres is healthy:

```bash
docker ps | grep public_health_postgres
# Should show: Up ... (healthy)
```

### 3. Run the full pipeline (easiest)

```bash
./scripts/run_pipeline.sh
```

This runs all four steps automatically: extract → clean → load → dbt.

---

### 3b. Or run each step manually

Use this if you want to understand each stage, or debug a single step.
All commands assume you are in the project folder with the venv activated.

```bash
source .venv/bin/activate
cd public-health-etl-pipeline   # your clone directory
```

#### Step A — Extract (download data from OWID)

Downloads real vaccination CSVs from Our World in Data. Requires internet.
Does **not** need Postgres.

```bash
PYTHONPATH=. python -m etl.extract.extract
```

Expected output:

```
  Downloading vaccination_coverage from OWID...
  Downloading dtp3 from OWID...
  vaccination_coverage: 9,203 rows
  dtp3: 9,174 rows
```

Files saved to:
- `data/raw/YYYY-MM-DD/` — dated snapshot
- `data/landing/` — working copy for the next step

#### Step B — Clean (standardise with pandas)

Validates values, standardises region names, flags missing data.
Does **not** need Postgres.

```bash
PYTHONPATH=. python -m etl.clean.clean
```

Expected output:

```json
{
  "indicator_rows": 36812,
  "region_count": 218,
  "country_count": 194,
  "null_values": 3767,
  "rejected_rows": 0,
  "revisions_detected": 0,
  "latest_dtp3_year": 2024,
  "countries_below_80pct_dtp3": 53
}
```

> Note: the reporting view `rpt_below_threshold` shows **47 countries** (non-null latest-year DTP3 in the warehouse).

Files saved to `data/cleaned/`.

#### Step C — Load (into PostgreSQL staging)

Requires Postgres to be running (`docker compose up -d postgres`).

```bash
PYTHONPATH=. python -m etl.load.load
```

Expected output:

```
  Loaded 36,812 rows into staging.stg_health_indicators
  Loaded 218 rows into staging.stg_regions
```

#### Step D — Transform (dbt star schema + tests)

Builds the warehouse and runs 15 data quality tests.

```bash
cd dbt
dbt deps --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .
cd ..
```

Expected: `Completed successfully` and `PASS=15`.

---

### 4. Verify everything works

```bash
# Postgres healthy
docker ps | grep public_health_postgres

# Reporting views have data
python scripts/verify_dashboard_data.py

# dbt tests pass
cd dbt && dbt test --profiles-dir . && cd ..
```

Expected verify output:

```
  trends: 9174 rows [OK]
  comparison: 194 rows [OK]
  below_threshold: 47 rows [OK]
Dashboard data layer verified.
```

### 5. View the dashboard (optional)

Streamlit is a web dashboard — a visual way to explore the data.
Skip this step if you prefer SQL only.

```bash
streamlit run reporting/streamlit/app.py
```

- Press **Enter** to skip the Streamlit email prompt
- Open **http://localhost:8501** in your browser
- You should see DTP3 trend charts and a table of countries below 80% coverage

Start Airflow (optional):

```bash
docker compose up -d
```

Airflow UI: http://localhost:8081 (admin / admin)

---

### 6. Query data with SQL

Connect to PostgreSQL:

```bash
# Via Docker (recommended)
docker exec -it public_health_postgres psql -U ph_user -d public_health_warehouse

# Or from the host (port 5433)
psql -h localhost -p 5433 -U ph_user -d public_health_warehouse
```

Password: `ph_pass` (from `.env`)

**Connection details:**

| Setting | Value |
|---------|-------|
| Container | `public_health_postgres` |
| Host port | `5433` |
| Database | `public_health_warehouse` |
| User | `ph_user` |
| Schemas | `staging`, `warehouse`, `reporting` |

**Useful psql commands:**

```sql
\dn                  -- list schemas
\dt staging.*        -- staging tables (pandas output)
\dt warehouse.*      -- star schema tables
\dv reporting.*      -- reporting views
\d warehouse.fact_health_indicator
\q                   -- quit
```

**Schema overview:**

| Schema | Contents | Example |
|--------|----------|---------|
| `staging` | Cleaned data loaded by pandas | `staging.stg_health_indicators` |
| `warehouse` | dbt star schema | `warehouse.fact_health_indicator`, `dim_region` |
| `reporting` | Analytics-ready views | `reporting.rpt_vaccination_trends` |

**Example queries:**

```sql
-- Staging: raw cleaned rows for one country
SELECT region_name, year, indicator_code, value
FROM staging.stg_health_indicators
WHERE region_name = 'South Africa' AND indicator_code = 'dtp3'
ORDER BY year DESC
LIMIT 10;

-- Warehouse: star schema join
SELECT dr.region_name, dd.year, di.indicator_name, f.value
FROM warehouse.fact_health_indicator f
JOIN warehouse.dim_region dr ON f.region_id = dr.region_key
JOIN warehouse.dim_date dd ON f.date_id = dd.date_id
JOIN warehouse.dim_indicator di ON f.indicator_id = di.indicator_code
WHERE dr.region_name = 'South Africa' AND di.indicator_code = 'dtp3'
ORDER BY dd.year DESC
LIMIT 10;

-- Reporting: countries below WHO 80% DTP3 target
SELECT * FROM reporting.rpt_below_threshold
ORDER BY dtp3_coverage_pct;

-- Reporting: latest-year regional comparison
SELECT * FROM reporting.rpt_regional_comparison
ORDER BY dtp3_coverage_pct DESC
LIMIT 20;
```

**One-liner from the terminal (no interactive psql):**

```bash
docker exec public_health_postgres psql -U ph_user -d public_health_warehouse \
  -c "SELECT count(*) AS fact_rows FROM warehouse.fact_health_indicator;"
```

---

## Command Reference

Quick lookup for all commands (venv must be activated):

| Goal | Command |
|------|---------|
| Activate venv | `source .venv/bin/activate` |
| Start Postgres | `docker compose up -d postgres` |
| Init database | `./scripts/init_db.sh` |
| **Full pipeline** | `./scripts/run_pipeline.sh` |
| Extract only | `PYTHONPATH=. python -m etl.extract.extract` |
| Clean only | `PYTHONPATH=. python -m etl.clean.clean` |
| Load only | `PYTHONPATH=. python -m etl.load.load` |
| dbt run + test | `cd dbt && dbt run --profiles-dir . && dbt test --profiles-dir .` |
| Verify data | `python scripts/verify_dashboard_data.py` |
| SQL shell | `docker exec -it public_health_postgres psql -U ph_user -d public_health_warehouse` |
| Dashboard | `streamlit run reporting/streamlit/app.py` |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'etl'` | Run with `PYTHONPATH=.` prefix, or use `./scripts/run_pipeline.sh` |
| `ModuleNotFoundError: No module named 'pandas'` | Activate venv: `source .venv/bin/activate` — don't use system `python3` |
| `Postgres container not running` | Run `docker compose up -d postgres` and wait ~10 seconds |
| `relation "staging.stg_health_indicators" does not exist` | Run `./scripts/init_db.sh` then re-run load |
| Streamlit email prompt | Press **Enter** to skip — email is optional |
| Port 5433 already in use | Stop other Postgres containers or change `POSTGRES_PORT` in `.env` |

---

## Prerequisites

- Python 3.10+
- Docker & Docker Compose
- Internet access (for OWID data download)

## Sample Insights

From the latest pipeline run (OWID / WHO-UNICEF data, 2024):

- **194 countries** tracked with DTP3 coverage data
- **47 countries** currently below the WHO 80% DTP3 target
- **3,767** country-year-indicator rows with missing values (preserved, not imputed)
- Coverage trends show steady global improvement since 1980, with persistent gaps in lower-income regions

## Dashboard Preview

DTP3 vaccination trends (selected countries):

![DTP3 vaccination trends](docs/screenshots/dtp3_trends.svg)

Regional comparison — latest year:

![Regional DTP3 comparison](docs/screenshots/regional_comparison.svg)

## Warehouse Model (Star Schema)

**Fact table:** `fact_health_indicator` — one row per region, year, and indicator

| Column | Description |
|--------|-------------|
| region_id | FK → dim_region |
| date_id | FK → dim_date |
| indicator_id | FK → dim_indicator |
| value | Coverage percentage |
| is_estimated | Flag for missing/revised figures |

**Dimensions:** `dim_region`, `dim_date`, `dim_indicator`

## Analytics Questions Answered

- How has DTP3 vaccination coverage trended over time by country?
- Which countries have the highest/lowest coverage in the latest year?
- Which countries fall below the WHO 80% DTP3 target?
- How do measles (MCV1) and polio coverage compare across regions?

## Project planning

- **Architecture (UML):** [GitHub Wiki](https://github.com/nkanyisoCode/public-health-etl-pipeline/wiki)
- **Iteration tickets:** [GitHub Issues](https://github.com/nkanyisoCode/public-health-etl-pipeline/issues) (milestones: Iteration 1–3)

## Data Quality

See [docs/DATA_QUALITY_REPORT.md](docs/DATA_QUALITY_REPORT.md) for documented issues and handling rules.

The pipeline includes:
- pandas validation (range checks, null handling, reject quarantine)
- Dated raw snapshots for revision detection
- dbt tests (uniqueness, not-null, referential integrity, value ranges)
- `staging.stg_rejected_rows` and `staging.stg_data_revisions` audit tables

## Data Source

- [OWID — Childhood vaccination coverage](https://ourworldindata.org/grapher/vaccination-coverage-who-unicef)
- [OWID — DTP3 immunization](https://ourworldindata.org/grapher/share-of-children-immunized-dtp3)
- License: Creative Commons BY — aggregate public data, no privacy concerns

## License

Educational portfolio project using publicly available aggregate health statistics.
