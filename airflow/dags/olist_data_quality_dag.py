"""Data-quality DAG: validate cleaned Parquet and fail loudly on regressions."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

default_args = {"owner": "analytics", "retries": 0}


@dag(
    dag_id="olist_data_quality",
    default_args=default_args,
    schedule="30 4 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["olist", "quality"],
)
def data_quality_dag():
    @task
    def validate() -> dict:
        from eap.quality import validate_all

        report = validate_all()
        if not report.success:
            failures = [f"{f.table}.{f.check}: {f.detail}" for f in report.failed]
            raise ValueError("Data quality checks failed: " + "; ".join(failures))
        return report.summary()

    validate()


data_quality_dag()
