"""Catalog invariants: every spec is internally consistent."""

import pytest

from eap.config import CATALOG, LOAD_ORDER, all_specs


@pytest.mark.unit
def test_load_order_covers_catalog() -> None:
    assert set(LOAD_ORDER) == set(CATALOG)


@pytest.mark.unit
def test_all_specs_ordered() -> None:
    assert [s.name for s in all_specs()] == list(LOAD_ORDER)


@pytest.mark.unit
def test_fk_targets_exist_in_catalog() -> None:
    for spec in CATALOG.values():
        for target in spec.foreign_keys.values():
            parent, _, col = target.partition(".")
            assert parent in CATALOG, f"{spec.name}: unknown FK parent {parent}"
            assert col, f"{spec.name}: FK target missing column: {target}"


@pytest.mark.unit
def test_orders_has_expected_timestamps() -> None:
    orders = CATALOG["orders"]
    assert "order_purchase_timestamp" in orders.timestamp_columns
    assert orders.primary_key == ("order_id",)


@pytest.mark.unit
def test_composite_key_flag() -> None:
    assert CATALOG["order_items"].is_composite_key
    assert not CATALOG["customers"].is_composite_key
