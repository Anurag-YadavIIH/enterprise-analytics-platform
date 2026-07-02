"""Acquire the raw Olist dataset.

Two strategies, tried in order:

1. **Kaggle API** — used when ``KAGGLE_USERNAME``/``KAGGLE_KEY`` are set
   (or a ``~/.kaggle/kaggle.json`` exists). Downloads and unzips the dataset
   into ``data/raw``.
2. **Local zip fallback** — if credentials are absent, any ``*.zip`` already
   present in ``data/raw`` is extracted. This keeps CI and offline runs green
   without network access.

The module never raises on "already present" — it is idempotent.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from eap.config import Settings, get_settings
from eap.utils.logging import get_logger

log = get_logger(__name__)

EXPECTED_FILES = {
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
}


def _already_downloaded(raw_dir: Path) -> bool:
    present = {p.name for p in raw_dir.glob("*.csv")}
    return EXPECTED_FILES.issubset(present)


def _extract_local_zips(raw_dir: Path) -> bool:
    """Extract any local zips in ``raw_dir``. Return True if any extracted."""
    zips = list(raw_dir.glob("*.zip"))
    if not zips:
        return False
    for archive in zips:
        log.info("download.extract_zip", archive=str(archive))
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(raw_dir)
    return True


def _download_from_kaggle(settings: Settings) -> bool:
    """Download via the Kaggle API. Return True on success, False if unavailable."""
    try:
        # Import lazily so the dependency is optional.
        from kaggle.api.kaggle_api_extended import KaggleApi  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dep
        log.warning("download.kaggle_unavailable", error=str(exc))
        return False

    if settings.kaggle_username and settings.kaggle_key:
        import os

        os.environ.setdefault("KAGGLE_USERNAME", settings.kaggle_username)
        os.environ.setdefault("KAGGLE_KEY", settings.kaggle_key)

    try:
        api = KaggleApi()
        api.authenticate()
        log.info("download.kaggle_start", dataset=settings.kaggle_dataset)
        api.dataset_download_files(
            settings.kaggle_dataset, path=str(settings.raw_dir), unzip=True, quiet=False
        )
        return True
    except Exception as exc:  # pragma: no cover - network/credential dependent
        log.warning("download.kaggle_failed", error=str(exc))
        return False


def download(settings: Settings | None = None, *, force: bool = False) -> Path:
    """Ensure the raw Olist CSVs exist in ``data/raw`` and return that dir."""
    settings = settings or get_settings()
    settings.ensure_dirs()
    raw_dir = settings.raw_dir

    if not force and _already_downloaded(raw_dir):
        log.info("download.skip", reason="all files present", raw_dir=str(raw_dir))
        return raw_dir

    if _download_from_kaggle(settings) and _already_downloaded(raw_dir):
        log.info("download.complete", source="kaggle", raw_dir=str(raw_dir))
        return raw_dir

    if _extract_local_zips(raw_dir) and _already_downloaded(raw_dir):
        log.info("download.complete", source="local-zip", raw_dir=str(raw_dir))
        return raw_dir

    missing = EXPECTED_FILES - {p.name for p in raw_dir.glob("*.csv")}
    if missing:
        raise FileNotFoundError(
            "Could not acquire the Olist dataset. "
            "Set KAGGLE_USERNAME/KAGGLE_KEY, or place the dataset zip in "
            f"{raw_dir}. Missing files: {sorted(missing)}"
        )
    return raw_dir


if __name__ == "__main__":  # pragma: no cover
    download()
