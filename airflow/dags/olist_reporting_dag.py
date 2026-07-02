"""Reporting DAG: refresh the DuckDB warehouse and export BI extracts."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

default_args = {"owner": "analytics", "retries": 1, "retry_delay": timedelta(minutes=2)}


@dag(
    dag_id="olist_reporting",
    default_args=default_args,
    schedule="0 5 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["olist", "reporting"],
)
def reporting_dag():
    @task
    def build_warehouse() -> str:
        from eap.warehouse import build_warehouse

        return str(build_warehouse())

    @task
    def export_extracts(db_path: str) -> str:
        """Export a monthly-revenue CSV extract for BI tools."""
        from pathlib import Path

        import duckdb

        out = Path("data/warehouse/monthly_revenue_extract.csv")
        con = duckdb.connect(db_path, read_only=True)
        try:
            df = con.execute(
                """
                SELECT strftime(order_purchase_timestamp, '%Y-%m') AS month,
                       COUNT(*) AS orders
                FROM fact_orders GROUP BY 1 ORDER BY 1
                """
            ).fetchdf()
        finally:
            con.close()
        df.to_csv(out, index=False)
        return str(out)

    export_extracts(build_warehouse())


reporting_dag()
