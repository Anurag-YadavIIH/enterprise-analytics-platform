"""PySpark transformation job: build a wide, analytics-ready order fact.

Demonstrates join optimisation on Spark:

* **broadcast joins** for the small dimension tables (products, sellers)
* aggregation of order items to one row per order before joining
* a single wide ``fact_orders_enriched`` Parquet output the BI layer can read

This is intentionally separate from ``csv_to_parquet`` so the raw-clean and
the modelling steps can be scheduled and cached independently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from eap.config import get_settings
from eap.utils.io import timer
from eap.utils.logging import get_logger
from spark_jobs.session import spark_session

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame, SparkSession

log = get_logger("spark.transformations")


def _read(spark: "SparkSession", name: str) -> "DataFrame":
    path = get_settings().parquet_dir / name
    return spark.read.parquet(str(path))


def build_order_facts(spark: "SparkSession") -> "DataFrame":
    from pyspark.sql import functions as F

    orders = _read(spark, "orders")
    items = _read(spark, "order_items")
    payments = _read(spark, "order_payments")
    products = _read(spark, "products")

    # Aggregate order items to order grain (one row per order).
    items_agg = items.groupBy("order_id").agg(
        F.countDistinct("product_id").alias("distinct_products"),
        F.count("order_item_id").alias("item_count"),
        F.round(F.sum("price"), 2).alias("items_value"),
        F.round(F.sum("freight_value"), 2).alias("freight_value"),
    )

    payments_agg = payments.groupBy("order_id").agg(
        F.round(F.sum("payment_value"), 2).alias("payment_value"),
        F.max("payment_installments").alias("max_installments"),
    )

    # Broadcast the small product dimension for the item->category rollup.
    item_categories = (
        items.join(F.broadcast(products.select("product_id", "product_category_name")), "product_id")
        .groupBy("order_id")
        .agg(F.first("product_category_name", ignorenulls=True).alias("primary_category"))
    )

    enriched = (
        orders.join(items_agg, "order_id", "left")
        .join(payments_agg, "order_id", "left")
        .join(item_categories, "order_id", "left")
        .withColumn(
            "delivery_days",
            F.datediff("order_delivered_customer_date", "order_purchase_timestamp"),
        )
        .withColumn("purchase_year", F.year("order_purchase_timestamp"))
        .withColumn("purchase_month", F.month("order_purchase_timestamp"))
    )
    return enriched


def run() -> str:
    """Build and persist the enriched order fact; return output path."""
    settings = get_settings()
    out = settings.parquet_dir / "fact_orders_enriched"
    with spark_session("eap-transformations") as spark, timer("spark:transformations"):
        enriched = build_order_facts(spark).cache()
        rows = enriched.count()
        (
            enriched.repartition("purchase_year", "purchase_month")
            .write.mode("overwrite")
            .partitionBy("purchase_year", "purchase_month")
            .parquet(str(out))
        )
        enriched.unpersist()
    log.info("spark.transformations_done", rows=rows, path=str(out))
    return str(out)


if __name__ == "__main__":  # pragma: no cover
    run()
