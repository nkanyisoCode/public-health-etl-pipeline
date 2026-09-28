"""Public health ETL pipeline DAG — download, clean, load, transform."""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="public_health_etl_pipeline",
    default_args=default_args,
    description="OWID vaccination data → staging → dbt warehouse",
    schedule_interval="@weekly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["public-health", "etl", "owid"],
) as dag:

    extract_task = BashOperator(
        task_id="extract",
        bash_command="cd /opt/airflow && python -m etl.extract.extract",
    )

    clean_task = BashOperator(
        task_id="clean",
        bash_command="cd /opt/airflow && python -m etl.clean.clean",
    )

    load_task = BashOperator(
        task_id="load_to_staging",
        bash_command="cd /opt/airflow && python -m etl.load.load",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/airflow/dbt && dbt deps --profiles-dir . && dbt run --profiles-dir .",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/airflow/dbt && dbt test --profiles-dir .",
    )

    extract_task >> clean_task >> load_task >> dbt_run >> dbt_test
