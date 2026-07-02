"""Dataset catalog for the Olist Brazilian e-commerce dataset.

A single source of truth describing every CSV: its filename, logical table
name, primary/foreign keys, timestamp columns and expected dtypes. The
ingestion, quality and warehouse layers all read from this catalog so that
schema knowledge lives in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TableSpec:
    """Declarative specification for one source table."""

    name: str
    csv_file: str
    primary_key: tuple[str, ...] = ()
    foreign_keys: dict[str, str] = field(default_factory=dict)  # column -> "table.column"
    timestamp_columns: tuple[str, ...] = ()
    numeric_columns: tuple[str, ...] = ()
    not_null_columns: tuple[str, ...] = ()

    @property
    def is_composite_key(self) -> bool:
        return len(self.primary_key) > 1


# ----------------------------------------------------------------------
# The nine core Olist files.
# ----------------------------------------------------------------------
CATALOG: dict[str, TableSpec] = {
    "customers": TableSpec(
        name="customers",
        csv_file="olist_customers_dataset.csv",
        primary_key=("customer_id",),
        not_null_columns=("customer_id", "customer_unique_id"),
    ),
    "geolocation": TableSpec(
        name="geolocation",
        csv_file="olist_geolocation_dataset.csv",
        numeric_columns=("geolocation_lat", "geolocation_lng"),
        not_null_columns=("geolocation_zip_code_prefix",),
    ),
    "order_items": TableSpec(
        name="order_items",
        csv_file="olist_order_items_dataset.csv",
        primary_key=("order_id", "order_item_id"),
        foreign_keys={
            "order_id": "orders.order_id",
            "product_id": "products.product_id",
            "seller_id": "sellers.seller_id",
        },
        timestamp_columns=("shipping_limit_date",),
        numeric_columns=("price", "freight_value"),
        not_null_columns=("order_id", "product_id", "seller_id"),
    ),
    "order_payments": TableSpec(
        name="order_payments",
        csv_file="olist_order_payments_dataset.csv",
        primary_key=("order_id", "payment_sequential"),
        foreign_keys={"order_id": "orders.order_id"},
        numeric_columns=("payment_installments", "payment_value"),
        not_null_columns=("order_id", "payment_type"),
    ),
    "order_reviews": TableSpec(
        name="order_reviews",
        csv_file="olist_order_reviews_dataset.csv",
        primary_key=("review_id",),
        foreign_keys={"order_id": "orders.order_id"},
        timestamp_columns=("review_creation_date", "review_answer_timestamp"),
        numeric_columns=("review_score",),
        not_null_columns=("review_id", "order_id"),
    ),
    "orders": TableSpec(
        name="orders",
        csv_file="olist_orders_dataset.csv",
        primary_key=("order_id",),
        foreign_keys={"customer_id": "customers.customer_id"},
        timestamp_columns=(
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ),
        not_null_columns=("order_id", "customer_id", "order_status"),
    ),
    "products": TableSpec(
        name="products",
        csv_file="olist_products_dataset.csv",
        primary_key=("product_id",),
        numeric_columns=(
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ),
        not_null_columns=("product_id",),
    ),
    "sellers": TableSpec(
        name="sellers",
        csv_file="olist_sellers_dataset.csv",
        primary_key=("seller_id",),
        not_null_columns=("seller_id",),
    ),
    "product_category_translation": TableSpec(
        name="product_category_translation",
        csv_file="product_category_name_translation.csv",
        primary_key=("product_category_name",),
        not_null_columns=("product_category_name",),
    ),
}

# Recommended load order so that FK targets exist before dependents.
LOAD_ORDER: tuple[str, ...] = (
    "customers",
    "sellers",
    "products",
    "product_category_translation",
    "geolocation",
    "orders",
    "order_items",
    "order_payments",
    "order_reviews",
)


def all_specs() -> list[TableSpec]:
    """Return all table specs in recommended load order."""
    return [CATALOG[name] for name in LOAD_ORDER]
