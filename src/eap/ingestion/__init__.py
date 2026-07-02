"""Ingestion package: acquire raw data and produce cleaned Parquet."""

from eap.ingestion.download import download
from eap.ingestion.ingest import IngestReport, ingest_all, ingest_one, ingest_table

__all__ = ["download", "IngestReport", "ingest_all", "ingest_one", "ingest_table"]
