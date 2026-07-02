"""Great Expectations integration.

Builds GE expectation suites from the dataset catalog so teams can generate
data docs and run the full GE flow. Kept separate from ``validate.py`` (which
is the fast, no-dependency path used by CI/Airflow). Import is lazy so the
package remains importable when GE is not installed.
"""

from __future__ import annotations

from typing import Any

from eap.config import CATALOG, TableSpec
from eap.utils.logging import get_logger

log = get_logger(__name__)


def build_suite_config(spec: TableSpec) -> dict[str, Any]:
    """Return a serialisable expectation-suite dict for one table.

    This is a plain data structure (not a live GE object) so it can be
    inspected and tested without importing GE. ``apply_suite`` turns it into
    real expectations against a GE validator.
    """
    expectations: list[dict[str, Any]] = []

    for col in spec.not_null_columns:
        expectations.append(
            {"expectation_type": "expect_column_values_to_not_be_null", "kwargs": {"column": col}}
        )

    if spec.primary_key and len(spec.primary_key) == 1:
        expectations.append(
            {
                "expectation_type": "expect_column_values_to_be_unique",
                "kwargs": {"column": spec.primary_key[0]},
            }
        )
    elif spec.primary_key:
        expectations.append(
            {
                "expectation_type": "expect_compound_columns_to_be_unique",
                "kwargs": {"column_list": list(spec.primary_key)},
            }
        )

    for col in ("price", "freight_value", "payment_value"):
        if col in spec.numeric_columns:
            expectations.append(
                {
                    "expectation_type": "expect_column_values_to_be_between",
                    "kwargs": {"column": col, "min_value": 0, "strict_min": False},
                }
            )

    if "review_score" in spec.numeric_columns:
        expectations.append(
            {
                "expectation_type": "expect_column_values_to_be_between",
                "kwargs": {"column": "review_score", "min_value": 1, "max_value": 5},
            }
        )

    return {"suite_name": f"{spec.name}_suite", "expectations": expectations}


def all_suite_configs() -> dict[str, dict[str, Any]]:
    """Build suite configs for every catalog table."""
    return {name: build_suite_config(spec) for name, spec in CATALOG.items()}


def apply_suite(validator: Any, config: dict[str, Any]) -> Any:  # pragma: no cover
    """Apply a suite config to a live GE validator instance."""
    for exp in config["expectations"]:
        method = getattr(validator, exp["expectation_type"])
        method(**exp["kwargs"])
    return validator
