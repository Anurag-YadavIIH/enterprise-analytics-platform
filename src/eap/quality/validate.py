"""Data-quality validation.

A lightweight, dependency-safe validation engine that expresses the same
expectations Great Expectations would (missing values, duplicate IDs, invalid
timestamps, primary/foreign keys, outliers). It reads the cleaned Parquet and
produces a structured :class:`ValidationReport`.

Great Expectations itself is wired via ``eap.quality.expectations`` for teams
that want the full GE data-docs experience; this module is what CI and the
Airflow quality DAG call because it is fast and has no external state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from eap.config import CATALOG, Settings, all_specs, get_settings
from eap.utils.io import read_parquet
from eap.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class CheckResult:
    table: str
    check: str
    passed: bool
    detail: str = ""


@dataclass
class ValidationReport:
    results: list[CheckResult] = field(default_factory=list)

    def add(self, table: str, check: str, passed: bool, detail: str = "") -> None:
        self.results.append(CheckResult(table, check, passed, detail))

    @property
    def failed(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]

    @property
    def success(self) -> bool:
        return not self.failed

    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.results),
            "passed": len(self.results) - len(self.failed),
            "failed": len(self.failed),
        }


def _load(table: str, settings: Settings) -> pd.DataFrame:
    return read_parquet(settings.processed_dir / f"{table}.parquet")


def _check_not_null(df: pd.DataFrame, spec, report: ValidationReport) -> None:
    for col in spec.not_null_columns:
        if col in df.columns:
            n_null = int(df[col].isna().sum())
            report.add(
                spec.name,
                f"not_null[{col}]",
                n_null == 0,
                f"{n_null} nulls" if n_null else "",
            )


def _check_primary_key(df: pd.DataFrame, spec, report: ValidationReport) -> None:
    if not spec.primary_key:
        return
    keys = list(spec.primary_key)
    if not all(k in df.columns for k in keys):
        report.add(spec.name, f"pk_present{keys}", False, "key column(s) missing")
        return
    dupes = int(df.duplicated(subset=keys).sum())
    report.add(spec.name, f"pk_unique{keys}", dupes == 0, f"{dupes} duplicate keys" if dupes else "")


def _check_foreign_keys(
    df: pd.DataFrame, spec, settings: Settings, report: ValidationReport
) -> None:
    for col, target in spec.foreign_keys.items():
        parent_table, parent_col = target.split(".")
        try:
            parent = _load(parent_table, settings)
        except FileNotFoundError:
            report.add(spec.name, f"fk[{col}->{target}]", False, "parent table missing")
            continue
        valid = set(parent[parent_col].dropna())
        child = df[col].dropna()
        orphans = int((~child.isin(valid)).sum())
        report.add(
            spec.name,
            f"fk[{col}->{target}]",
            orphans == 0,
            f"{orphans} orphan rows" if orphans else "",
        )


def _check_timestamps(df: pd.DataFrame, spec, report: ValidationReport) -> None:
    for col in spec.timestamp_columns:
        if col in df.columns:
            is_dt = pd.api.types.is_datetime64_any_dtype(df[col])
            report.add(spec.name, f"timestamp_type[{col}]", is_dt, "" if is_dt else "not datetime")


def _check_outliers(df: pd.DataFrame, spec, report: ValidationReport) -> None:
    """Flag negative values in monetary/quantity columns as invalid outliers."""
    monetary = {"price", "freight_value", "payment_value"}
    for col in spec.numeric_columns:
        if col in monetary and col in df.columns:
            n_neg = int((df[col] < 0).sum())
            report.add(spec.name, f"non_negative[{col}]", n_neg == 0, f"{n_neg} negatives" if n_neg else "")


def validate_table(table: str, settings: Settings | None = None) -> ValidationReport:
    """Validate a single table and return its report."""
    settings = settings or get_settings()
    spec = CATALOG[table]
    df = _load(table, settings)
    report = ValidationReport()
    _check_not_null(df, spec, report)
    _check_primary_key(df, spec, report)
    _check_foreign_keys(df, spec, settings, report)
    _check_timestamps(df, spec, report)
    _check_outliers(df, spec, report)
    return report


def validate_all(settings: Settings | None = None) -> ValidationReport:
    """Validate every catalog table into a single combined report."""
    settings = settings or get_settings()
    report = ValidationReport()
    for spec in all_specs():
        sub = validate_table(spec.name, settings)
        report.results.extend(sub.results)
    log.info("quality.validate_done", **report.summary())
    for failure in report.failed:
        log.warning("quality.check_failed", table=failure.table, check=failure.check, detail=failure.detail)
    return report


if __name__ == "__main__":  # pragma: no cover
    rep = validate_all()
    raise SystemExit(0 if rep.success else 1)
