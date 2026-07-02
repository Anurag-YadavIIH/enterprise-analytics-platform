"""Ingestion behaviour: cleaning, dedupe, typing, parquet output."""

import pandas as pd
import pytest

from eap.config import CATALOG, Settings
from eap.ingestion import ingest_all, ingest_one
from eap.utils.io import read_parquet


@pytest.mark.unit
def test_ingest_all_produces_every_table(ingested: Settings) -> None:
    for name in CATALOG:
        assert (ingested.processed_dir / f"{name}.parquet").exists(), name


@pytest.mark.unit
def test_duplicate_primary_keys_removed(ingested: Settings) -> None:
    customers = read_parquet(ingested.processed_dir / "customers.parquet")
    assert customers["customer_id"].is_unique
    assert len(customers) == 3  # raw had 4 rows, one dup key


@pytest.mark.unit
def test_timestamps_are_datetime(ingested: Settings) -> None:
    orders = read_parquet(ingested.processed_dir / "orders.parquet")
    for col in CATALOG["orders"].timestamp_columns:
        assert pd.api.types.is_datetime64_any_dtype(orders[col]), col


@pytest.mark.unit
def test_empty_strings_become_null(ingested: Settings) -> None:
    orders = read_parquet(ingested.processed_dir / "orders.parquet")
    # o3 had empty delivered dates in raw CSV
    o3 = orders.loc[orders["order_id"] == "o3"].iloc[0]
    assert pd.isna(o3["order_delivered_customer_date"])


@pytest.mark.unit
def test_ingest_one_unknown_table_raises(settings: Settings) -> None:
    with pytest.raises(KeyError):
        ingest_one("nope", settings)


@pytest.mark.unit
def test_report_row_accounting(settings: Settings) -> None:
    reports = ingest_all(settings)
    by_name = {r.table: r for r in reports}
    cust = by_name["customers"]
    assert cust.rows_in == 4
    assert cust.rows_out == 3
    assert cust.duplicates_removed == 1
    assert cust.rows_dropped == 1
