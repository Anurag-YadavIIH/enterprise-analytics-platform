"""Data-quality package: fast validation + Great Expectations suites."""

from eap.quality.expectations import all_suite_configs, build_suite_config
from eap.quality.validate import (
    CheckResult,
    ValidationReport,
    validate_all,
    validate_table,
)

__all__ = [
    "CheckResult",
    "ValidationReport",
    "all_suite_configs",
    "build_suite_config",
    "validate_all",
    "validate_table",
]
