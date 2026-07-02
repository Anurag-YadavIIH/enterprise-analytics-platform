"""Small reusable helpers shared across the platform."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from eap.utils.logging import get_logger

log = get_logger(__name__)


@contextmanager
def timer(stage: str) -> Iterator[None]:
    """Log wall-clock duration of a code block.

    >>> with timer("load"):
    ...     do_work()
    """
    start = time.perf_counter()
    log.info("stage.start", stage=stage)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        log.info("stage.done", stage=stage, seconds=round(elapsed, 3))


def ensure_dir(path: Path) -> Path:
    """Create ``path`` (and parents) if missing; return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def human_bytes(n: int) -> str:
    """Format a byte count as a human-readable string."""
    step = 1024.0
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < step:
            return f"{value:.1f}{unit}"
        value /= step
    return f"{value:.1f}PB"


def write_parquet(df: pd.DataFrame, path: Path, *, index: bool = False) -> Path:
    """Write a DataFrame to a single Parquet file with snappy compression."""
    ensure_dir(path.parent)
    df.to_parquet(path, engine="pyarrow", compression="snappy", index=index)
    log.info("parquet.write", path=str(path), rows=len(df))
    return path


def read_parquet(path: Path) -> pd.DataFrame:
    """Read a Parquet file (or partitioned directory) into a DataFrame."""
    return pd.read_parquet(path, engine="pyarrow")
