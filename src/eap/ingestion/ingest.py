"""Raw CSV -> cleaned Parquet ingestion (pandas reference implementation).

Responsibilities, driven entirely by the dataset catalog:

* read each CSV with correct dtypes
* trim/normalise string columns
* coerce declared timestamp columns to timezone-naive datetimes
* coerce declared numeric columns
* drop exact duplicate rows and duplicate primary keys
* write one Parquet file per table into ``data/processed``

The PySpark equivalent lives in ``spark_jobs/`` and shares this catalog, so
the two implementations stay in lockstep. This module is import-safe and
fully unit-testable without Spark.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from eap.config import CATALOG, Settings, TableSpec, all_specs, get_settings
from eap.utils.io import timer, write_parquet
from eap.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class IngestReport:
    """Per-table summary produced by :func:`ingest_table`."""

    table: str
    rows_in: int
    rows_out: int
    duplicates_removed: int
    output_path: Path

    @property
    def rows_dropped(self) -> int:
        return self.rows_in - self.rows_out


def _clean_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace and collapse empty strings to NA for object columns."""
    obj_cols = df.select_dtypes(include="object").columns
    for col in obj_cols:
        df[col] = df[col].astype("string").str.strip()
        df[col] = df[col].replace({"": pd.NA})
    return df


def _standardize_timestamps(df: pd.DataFrame, spec: TableSpec) -> pd.DataFrame:
    for col in spec.timestamp_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _coerce_numeric(df: pd.DataFrame, spec: TableSpec) -> pd.DataFrame:
    for col in spec.numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _dedupe(df: pd.DataFrame, spec: TableSpec) -> tuple[pd.DataFrame, int]:
    before = len(df)
    df = df.drop_duplicates()
    if spec.primary_key and all(k in df.columns for k in spec.primary_key):
        df = df.drop_duplicates(subset=list(spec.primary_key), keep="first")
    removed = before - len(df)
    return df, removed


def ingest_table(spec: TableSpec, settings: Settings | None = None) -> IngestReport:
    """Ingest a single table end-to-end and write cleaned Parquet."""
    settings = settings or get_settings()
    src = settings.raw_dir / spec.csv_file
    if not src.exists():
        raise FileNotFoundError(f"Expected raw file not found: {src}")

    with timer(f"ingest:{spec.name}"):
        df = pd.read_csv(src, dtype_backend="numpy_nullable")
        rows_in = len(df)

        df = _clean_strings(df)
        df = _standardize_timestamps(df, spec)
        df = _coerce_numeric(df, spec)
        df, duplicates = _dedupe(df, spec)

        out_path = settings.processed_dir / f"{spec.name}.parquet"
        write_parquet(df, out_path)

    report = IngestReport(
        table=spec.name,
        rows_in=rows_in,
        rows_out=len(df),
        duplicates_removed=duplicates,
        output_path=out_path,
    )
    log.info(
        "ingest.table_done",
        table=report.table,
        rows_in=report.rows_in,
        rows_out=report.rows_out,
        duplicates_removed=report.duplicates_removed,
    )
    return report


def ingest_all(settings: Settings | None = None) -> list[IngestReport]:
    """Ingest every catalog table in recommended load order."""
    settings = settings or get_settings()
    settings.ensure_dirs()
    reports = [ingest_table(spec, settings) for spec in all_specs()]
    total_out = sum(r.rows_out for r in reports)
    log.info("ingest.all_done", tables=len(reports), total_rows=total_out)
    return reports


def ingest_one(table: str, settings: Settings | None = None) -> IngestReport:
    """Ingest a single named table (validates against the catalog)."""
    if table not in CATALOG:
        raise KeyError(f"Unknown table '{table}'. Known: {sorted(CATALOG)}")
    return ingest_table(CATALOG[table], settings)


if __name__ == "__main__":  # pragma: no cover
    ingest_all()
