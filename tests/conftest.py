"""Shared pytest fixtures.

Creates a fully isolated environment per test session: a temp directory tree
with a small synthetic Olist dataset, and a Settings object pointed at it.
No network, no Kaggle, no Docker required — the suite runs anywhere.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eap.config import Settings


def _write_synthetic_raw(raw: Path) -> None:
    """Write a minimal but referentially consistent Olist dataset."""
    raw.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        {
            "customer_id": ["c1", "c2", "c3", "c3"],  # duplicate pk on purpose
            "customer_unique_id": ["u1", "u2", "u3", "u3"],
            "customer_zip_code_prefix": [1001, 1002, 1003, 1003],
            "customer_city": ["sao paulo", "rio", "bh", "bh"],
            "customer_state": ["SP", "RJ", "MG", "MG"],
        }
    ).to_csv(raw / "olist_customers_dataset.csv", index=False)

    pd.DataFrame(
        {
            "seller_id": ["s1", "s2"],
            "seller_zip_code_prefix": [2001, 2002],
            "seller_city": ["campinas", "curitiba"],
            "seller_state": ["SP", "PR"],
        }
    ).to_csv(raw / "olist_sellers_dataset.csv", index=False)

    pd.DataFrame(
        {
            "product_id": ["p1", "p2"],
            "product_category_name": ["moveis", "eletronicos"],
            "product_name_lenght": [40, 50],
            "product_description_lenght": [200, 300],
            "product_photos_qty": [1, 2],
            "product_weight_g": [500, 1500],
            "product_length_cm": [20, 30],
            "product_height_cm": [10, 15],
            "product_width_cm": [15, 20],
        }
    ).to_csv(raw / "olist_products_dataset.csv", index=False)

    pd.DataFrame(
        {
            "product_category_name": ["moveis", "eletronicos"],
            "product_category_name_english": ["furniture", "electronics"],
        }
    ).to_csv(raw / "product_category_name_translation.csv", index=False)

    pd.DataFrame(
        {
            "geolocation_zip_code_prefix": [1001, 1002, 1003],
            "geolocation_lat": [-23.5, -22.9, -19.9],
            "geolocation_lng": [-46.6, -43.2, -43.9],
            "geolocation_city": ["sao paulo", "rio", "bh"],
            "geolocation_state": ["SP", "RJ", "MG"],
        }
    ).to_csv(raw / "olist_geolocation_dataset.csv", index=False)

    pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3"],
            "customer_id": ["c1", "c2", "c3"],
            "order_status": ["delivered", "delivered", "shipped"],
            "order_purchase_timestamp": [
                "2018-01-05 10:00:00",
                "2018-02-10 14:30:00",
                "2018-02-11 09:00:00",
            ],
            "order_approved_at": [
                "2018-01-05 10:15:00",
                "2018-02-10 15:00:00",
                "2018-02-11 09:20:00",
            ],
            "order_delivered_carrier_date": ["2018-01-06 08:00:00", "2018-02-11 08:00:00", ""],
            "order_delivered_customer_date": ["2018-01-10 16:00:00", "2018-02-15 12:00:00", ""],
            "order_estimated_delivery_date": [
                "2018-01-12 00:00:00",
                "2018-02-20 00:00:00",
                "2018-02-25 00:00:00",
            ],
        }
    ).to_csv(raw / "olist_orders_dataset.csv", index=False)

    pd.DataFrame(
        {
            "order_id": ["o1", "o1", "o2", "o3"],
            "order_item_id": [1, 2, 1, 1],
            "product_id": ["p1", "p2", "p1", "p2"],
            "seller_id": ["s1", "s2", "s1", "s2"],
            "shipping_limit_date": ["2018-01-08", "2018-01-08", "2018-02-13", "2018-02-14"],
            "price": [100.0, 50.0, 100.0, 200.0],
            "freight_value": [10.0, 5.0, 10.0, 20.0],
        }
    ).to_csv(raw / "olist_order_items_dataset.csv", index=False)

    pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3"],
            "payment_sequential": [1, 1, 1],
            "payment_type": ["credit_card", "boleto", "credit_card"],
            "payment_installments": [3, 1, 2],
            "payment_value": [165.0, 110.0, 220.0],
        }
    ).to_csv(raw / "olist_order_payments_dataset.csv", index=False)

    pd.DataFrame(
        {
            "review_id": ["r1", "r2", "r3"],
            "order_id": ["o1", "o2", "o3"],
            "review_score": [5, 4, 3],
            "review_creation_date": ["2018-01-11", "2018-02-16", "2018-02-20"],
            "review_answer_timestamp": [
                "2018-01-12 10:00:00",
                "2018-02-17 11:00:00",
                "2018-02-21 09:00:00",
            ],
        }
    ).to_csv(raw / "olist_order_reviews_dataset.csv", index=False)


@pytest.fixture(scope="session")
def settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    """Isolated settings with synthetic raw data on disk."""
    root = tmp_path_factory.mktemp("eap")
    s = Settings(
        EAP_DATA_RAW=root / "raw",
        EAP_DATA_PROCESSED=root / "processed",
        EAP_DATA_PARQUET=root / "parquet",
        EAP_DATA_WAREHOUSE=root / "warehouse",
        EAP_DUCKDB_PATH=root / "warehouse" / "olist.duckdb",
    )
    s.ensure_dirs()
    _write_synthetic_raw(s.raw_dir)
    return s


@pytest.fixture(scope="session")
def ingested(settings: Settings) -> Settings:
    """Settings after running the full ingestion."""
    from eap.ingestion import ingest_all

    ingest_all(settings)
    return settings


@pytest.fixture(scope="session")
def warehouse(ingested: Settings) -> Settings:
    """Settings after building the DuckDB star schema."""
    from eap.warehouse import build_warehouse

    build_warehouse(ingested)
    return ingested
