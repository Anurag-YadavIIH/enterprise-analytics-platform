"""Data-quality engine behaviour."""

import pandas as pd
import pytest

from eap.config import Settings
from eap.quality import build_suite_config, validate_all, validate_table
from eap.quality.validate import ValidationReport


@pytest.mark.unit
def test_validate_all_passes_on_clean_data(ingested: Settings) -> None:
    report = validate_all(ingested)
    assert report.success, [f"{f.table}.{f.check}" for f in report.failed]
    assert report.summary()["failed"] == 0


@pytest.mark.unit
def test_validate_detects_orphan_fk(ingested: Settings) -> None:
    # Corrupt order_items with an orphan order_id, revalidate.
    path = ingested.processed_dir / "order_items.parquet"
    df = pd.read_parquet(path)
    bad = df.iloc[[0]].copy()
    bad["order_id"] = "GHOST"
    bad["order_item_id"] = 99
    pd.concat([df, bad]).to_parquet(path, index=False)
    try:
        report = validate_table("order_items", ingested)
        fk_checks = [r for r in report.results if r.check.startswith("fk[order_id")]
        assert fk_checks and not fk_checks[0].passed
    finally:
        df.to_parquet(path, index=False)  # restore


@pytest.mark.unit
def test_report_summary_math() -> None:
    r = ValidationReport()
    r.add("t", "a", True)
    r.add("t", "b", False, "boom")
    assert r.summary() == {"total": 2, "passed": 1, "failed": 1}
    assert not r.success


@pytest.mark.unit
def test_ge_suite_config_shapes() -> None:
    from eap.config import CATALOG

    cfg = build_suite_config(CATALOG["order_reviews"])
    types = {e["expectation_type"] for e in cfg["expectations"]}
    assert "expect_column_values_to_not_be_null" in types
    assert "expect_column_values_to_be_unique" in types
    # review_score bounded 1..5
    bounded = [e for e in cfg["expectations"] if e["kwargs"].get("column") == "review_score"]
    assert bounded and bounded[0]["kwargs"]["max_value"] == 5
