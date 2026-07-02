"""Standalone ingestion DAG: acquire + clean raw Olist data.

Runs more frequently than the full pipeline so cleaned Parquet is always
fresh for downstream consumers. Uses the TaskFlow API and calls into the
tested ``eap`` package directly rather than shelling out.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

default_args = {"owner": "analytics", "retries": 1, "retry_delay": timedelta(minutes=2)}


@dag(
    dag_id="olist_ingestion",
    default_args=default_args,
    schedule="0 */6 * * *",  # every 6 hours
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["olist", "ingestion"],
)
def ingestion_dag():
    @task
    def download() -> str:
        from eap.ingestion import download as dl

        return str(dl())

    @task
    def ingest(raw_dir: str) -> dict:
        from eap.ingestion import ingest_all

        reports = ingest_all()
        return {r.table: r.rows_out for r in reports}

    @task
    def summarize(counts: dict) -> None:
        from eap.utils.logging import get_logger

        get_logger("airflow.ingestion").info("ingestion.summary", **counts)

    summarize(ingest(download()))


ingestion_dag()
