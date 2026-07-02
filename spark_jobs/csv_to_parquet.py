"""PySpark job: read raw Olist CSVs, clean, and write partitioned Parquet.

Mirrors the pandas ingestion (same catalog) but at scale:

* schema-driven casting of timestamp / numeric columns
* trim string columns, null-out empties
* drop duplicate rows and duplicate primary keys
* partition the large ``orders`` fact by purchase year/month
* Snappy Parquet output under ``data/parquet``

Best practices demonstrated: explicit column casting, ``dropDuplicates`` on
keys, ``repartition`` before partitioned writes, and ``cache`` where a frame is
reused for both a write and a count/log.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from eap.config import CATALOG, TableSpec, get_settings
from eap.utils.io import timer
from eap.utils.logging import get_logger
from spark_jobs.session import spark_session

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame, SparkSession

log = get_logger("spark.csv_to_parquet")

# Tables large enough to benefit from physical partitioning on write.
PARTITIONED = {"orders": ["purchase_year", "purchase_month"]}


def _clean(df: "DataFrame", spec: TableSpec) -> "DataFrame":
    from pyspark.sql import functions as F
    from pyspark.sql.types import StringType

    # Trim strings, convert empty -> null
    for field in df.schema.fields:
        if isinstance(field.dataType, StringType):
            col = F.trim(F.col(field.name))
            df = df.withColumn(field.name, F.when(col == "", None).otherwise(col))

    # Timestamps
    for col in spec.timestamp_columns:
        if col in df.columns:
            df = df.withColumn(col, F.to_timestamp(F.col(col)))

    # Numerics
    for col in spec.numeric_columns:
        if col in df.columns:
            df = df.withColumn(col, F.col(col).cast("double"))

    # Deduplicate
    df = df.dropDuplicates()
    if spec.primary_key and all(k in df.columns for k in spec.primary_key):
        df = df.dropDuplicates(list(spec.primary_key))
    return df


def _augment_orders(df: "DataFrame") -> "DataFrame":
    from pyspark.sql import functions as F

    return df.withColumn("purchase_year", F.year("order_purchase_timestamp")).withColumn(
        "purchase_month", F.month("order_purchase_timestamp")
    )


def process_table(spark: "SparkSession", spec: TableSpec) -> int:
    """Process one table CSV -> Parquet; return the output row count."""
    from pyspark.sql import functions as F

    settings = get_settings()
    src = settings.raw_dir / spec.csv_file
    out = settings.parquet_dir / spec.name

    with timer(f"spark:{spec.name}"):
        df = (
            spark.read.option("header", True)
            .option("inferSchema", True)
            .option("multiLine", True)
            .option("escape", '"')
            .csv(str(src))
        )
        df = _clean(df, spec)

        if spec.name in PARTITIONED:
            part_cols = PARTITIONED[spec.name]
            writer = _augment_orders(df).cache()
            n = writer.count()  # materialise cache
            (
                writer.repartition(*[F.col(c) for c in part_cols])
                .write.mode("overwrite")
                .partitionBy(*part_cols)
                .parquet(str(out))
            )
            writer.unpersist()
        else:
            writer = df.cache()
            n = writer.count()
            writer.write.mode("overwrite").parquet(str(out))
            writer.unpersist()

    log.info("spark.table_written", table=spec.name, rows=n, path=str(out))
    return n


def run(tables: list[str] | None = None) -> dict[str, int]:
    """Run the CSV->Parquet job for the given tables (default: all)."""
    names = tables or list(CATALOG.keys())
    results: dict[str, int] = {}
    with spark_session("eap-csv-to-parquet") as spark:
        for name in names:
            results[name] = process_table(spark, CATALOG[name])
    log.info("spark.csv_to_parquet_done", tables=len(results), total_rows=sum(results.values()))
    return results


if __name__ == "__main__":  # pragma: no cover
    run()
