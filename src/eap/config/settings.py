"""Typed application settings loaded from environment / .env.

All configuration flows through :func:`get_settings`, which is cached so the
same object is reused across the process. Nothing in the codebase reads
``os.environ`` directly — this keeps configuration testable and explicit.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor for the default (relative) data paths below. Resolving this from
# __file__ only works for an *editable* install (src/eap/config/settings.py
# living inside the repo); a regular `pip install .` copies the package into
# site-packages, so __file__-based anchoring silently points at the Python
# install dir instead of the app's working directory. The current working
# directory is what every entrypoint (the `eap` CLI, uvicorn, streamlit,
# Docker's WORKDIR) actually runs from, so anchor there instead.
REPO_ROOT = Path.cwd()


class Settings(BaseSettings):
    """Central, validated configuration object."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = Field(default="local", alias="EAP_ENV")

    # --- Paths (relative resolved against repo root) ---
    data_raw: Path = Field(default=Path("data/raw"), alias="EAP_DATA_RAW")
    data_processed: Path = Field(default=Path("data/processed"), alias="EAP_DATA_PROCESSED")
    data_parquet: Path = Field(default=Path("data/parquet"), alias="EAP_DATA_PARQUET")
    data_warehouse: Path = Field(default=Path("data/warehouse"), alias="EAP_DATA_WAREHOUSE")

    # --- Kaggle ---
    kaggle_dataset: str = Field(default="olistbr/brazilian-ecommerce", alias="KAGGLE_DATASET")
    kaggle_username: str | None = Field(default=None, alias="KAGGLE_USERNAME")
    kaggle_key: str | None = Field(default=None, alias="KAGGLE_KEY")

    # --- PostgreSQL ---
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="olist", alias="POSTGRES_DB")
    postgres_user: str = Field(default="analytics", alias="POSTGRES_USER")
    postgres_password: str = Field(default="analytics", alias="POSTGRES_PASSWORD")
    warehouse_url_override: str | None = Field(default=None, alias="EAP_WAREHOUSE_URL")

    # --- DuckDB ---
    duckdb_path: Path = Field(default=Path("data/warehouse/olist.duckdb"), alias="EAP_DUCKDB_PATH")

    # --- Spark ---
    spark_master: str = Field(default="local[*]", alias="SPARK_MASTER")
    spark_app_name: str = Field(default="eap-spark", alias="SPARK_APP_NAME")
    spark_shuffle_partitions: int = Field(default=8, alias="SPARK_SHUFFLE_PARTITIONS")

    # --- API ---
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_title: str = Field(default="Olist Analytics API", alias="API_TITLE")

    # --- Logging ---
    log_level: str = Field(default="INFO", alias="EAP_LOG_LEVEL")
    log_json: bool = Field(default=False, alias="EAP_LOG_JSON")

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------
    def _abs(self, p: Path) -> Path:
        return p if p.is_absolute() else (REPO_ROOT / p)

    @property
    def raw_dir(self) -> Path:
        return self._abs(self.data_raw)

    @property
    def processed_dir(self) -> Path:
        return self._abs(self.data_processed)

    @property
    def parquet_dir(self) -> Path:
        return self._abs(self.data_parquet)

    @property
    def warehouse_dir(self) -> Path:
        return self._abs(self.data_warehouse)

    @property
    def duckdb_file(self) -> Path:
        return self._abs(self.duckdb_path)

    @computed_field  # type: ignore[misc]
    @property
    def warehouse_url(self) -> str:
        """SQLAlchemy URL for the PostgreSQL analytics warehouse."""
        if self.warehouse_url_override:
            return self.warehouse_url_override
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def ensure_dirs(self) -> None:
        """Create all managed data directories if they do not exist."""
        for d in (self.raw_dir, self.processed_dir, self.parquet_dir, self.warehouse_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached, process-wide settings instance."""
    return Settings()
