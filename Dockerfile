# ETL application image
# Installs pipeline dependencies and runs the full pipeline by default.
# Override CMD to run individual stages:
#   docker run etl python -m etl.extract.extract
#   docker run etl python -m etl.clean.clean
#   docker run etl python -m etl.load.load

FROM python:3.11-slim

WORKDIR /app

# gcc + libpq-dev required by psycopg2-binary on some base images
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev bash \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt

COPY etl/       ./etl/
COPY dbt/       ./dbt/
COPY data/      ./data/
COPY scripts/   ./scripts/

# Copy example env so the container starts without a mounted .env
COPY .env.example .env

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

CMD ["bash", "scripts/run_pipeline.sh"]
