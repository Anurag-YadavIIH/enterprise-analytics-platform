"""Master Airflow DAG orchestrating the full Olist analytics pipeline.

download -> ingest -> spark transform -> warehouse build -> dbt build ->
data-quality validation -> reporting refresh.

Uses the ``eap`` CLI and dbt via BashOperator so the DAG stays thin and the
logic remains in the tested Python package. Schedule: daily. Backfill-safe
because every task is idempotent.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator

default_args = {
    "owner": "analytics",
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
    "depends_on_past": False,
}

with DAG(
    dag_id="olist_pipeline",
    description="End-to-end Olist analytics pipeline",
    default_args=default_args,
    schedule="0 4 * * *",  # daily at 04:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["olist", "elt", "analytics"],
) as dag:
    start = EmptyOperator(task_id="start")

    download = BashOperator(
        task_id="download",
        bash_command="eap ingest download",
    )

    ingest = BashOperator(
        task_id="ingest",
        bash_command="eap ingest run --skip-download",
    )

    spark_transform = BashOperator(
        task_id="spark_transform",
        bash_command="eap spark run-all",
    )

    warehouse = BashOperator(
        task_id="warehouse_build",
        bash_command="eap warehouse build",
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command="cd $AIRFLOW_HOME/../dbt/olist && dbt build --target duckdb",
    )

    quality = BashOperator(
        task_id="data_quality",
        bash_command="eap quality validate",
    )

    end = EmptyOperator(task_id="end")

    start >> download >> ingest >> spark_transform >> warehouse >> dbt_build >> quality >> end
