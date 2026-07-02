"""Execute every query in sql/queries/*.sql against the DuckDB warehouse.

Splits each file on ';' into individual statements, associates each with its
preceding '-- Qn.' label, skips comment-only fragments, and runs the rest
read-only. Reports per-file pass/fail and flags queries that return zero rows
(not a failure, but often worth a second look).

Usage::

    python scripts/run_sql_library.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
QUERIES_DIR = REPO_ROOT / "sql" / "queries"
DB_PATH = REPO_ROOT / "data" / "warehouse" / "olist.duckdb"

Q_LABEL_RE = re.compile(r"--\s*(Q\d+)\.", re.IGNORECASE)


def _statements(sql_text: str) -> list[tuple[str, str]]:
    """Split file text into (label, statement) pairs, skipping empty chunks."""
    out: list[tuple[str, str]] = []
    for chunk in sql_text.split(";"):
        label_match = Q_LABEL_RE.search(chunk)
        code_lines = [
            line
            for line in chunk.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ]
        if not code_lines:
            continue
        label = label_match.group(1) if label_match else "?"
        out.append((label, chunk.strip()))
    return out


def main() -> int:
    if not DB_PATH.exists():
        print(f"Warehouse not found at {DB_PATH}. Run `eap warehouse build` first.")
        return 1

    con = duckdb.connect(str(DB_PATH), read_only=True)
    total = 0
    failures: list[tuple[str, str, str]] = []
    zero_row: list[tuple[str, str]] = []

    for path in sorted(QUERIES_DIR.glob("*.sql")):
        statements = _statements(path.read_text(encoding="utf-8"))
        file_failures = 0
        for label, stmt in statements:
            total += 1
            try:
                rows = con.execute(stmt).fetchall()
                if len(rows) == 0:
                    zero_row.append((path.name, label))
            except Exception as exc:  # noqa: BLE001 - report every failure mode
                file_failures += 1
                failures.append((path.name, label, str(exc)))
        status = "OK" if file_failures == 0 else f"{file_failures} FAILED"
        print(f"{path.name}: {len(statements)} queries — {status}")

    con.close()

    print(f"\n{total} queries executed, {len(failures)} failed, {len(zero_row)} returned zero rows.")

    if zero_row:
        print("\nZero-row results (not failures, but worth reviewing):")
        for fname, label in zero_row:
            print(f"  {fname} {label}")

    if failures:
        print("\nFailures:")
        for fname, label, err in failures:
            print(f"  {fname} {label}: {err.splitlines()[0]}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
