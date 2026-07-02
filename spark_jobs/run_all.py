"""Orchestrate all Spark jobs in order: CSV->Parquet, then transformations."""

from __future__ import annotations

from eap.utils.logging import get_logger

log = get_logger("spark.run_all")


def main() -> None:
    """Run the full Spark pipeline."""
    from spark_jobs import csv_to_parquet, transformations

    log.info("spark.pipeline_start")
    counts = csv_to_parquet.run()
    out = transformations.run()
    log.info("spark.pipeline_done", table_counts=counts, enriched_output=out)


if __name__ == "__main__":
    main()
