"""SparkSession factory with sensible, tunable defaults.

Centralises Spark configuration so every job shares the same session builder:
adaptive query execution, tuned shuffle partitions, Arrow-based pandas
conversion and Snappy Parquet output.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

from eap.config import get_settings
from eap.utils.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import SparkSession

log = get_logger("spark.session")


def build_spark(app_name: str | None = None) -> "SparkSession":
    """Create (or fetch) a configured SparkSession."""
    from pyspark.sql import SparkSession

    settings = get_settings()
    builder = (
        SparkSession.builder.appName(app_name or settings.spark_app_name)
        .master(settings.spark_master)
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.shuffle.partitions", str(settings.spark_shuffle_partitions))
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.showConsoleProgress", "false")
    )
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    log.info(
        "spark.session_ready",
        app=spark.sparkContext.appName,
        master=settings.spark_master,
        shuffle_partitions=settings.spark_shuffle_partitions,
    )
    return spark


@contextmanager
def spark_session(app_name: str | None = None) -> Iterator["SparkSession"]:
    """Context manager that stops the session on exit."""
    spark = build_spark(app_name)
    try:
        yield spark
    finally:
        spark.stop()
        log.info("spark.session_stopped")
