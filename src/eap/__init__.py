"""Enterprise Analytics Platform (eap).

A modular, end-to-end retail analytics platform built on the Olist
Brazilian e-commerce dataset. Sub-packages:

- ``eap.config``     : typed settings + dataset catalog
- ``eap.utils``      : logging, timing, IO helpers
- ``eap.ingestion``  : download + raw CSV ingestion
- ``eap.quality``    : Great Expectations validation
- ``eap.warehouse``  : star-schema builder (DuckDB)
"""

from __future__ import annotations

__version__ = "1.0.0"

__all__ = ["__version__"]
