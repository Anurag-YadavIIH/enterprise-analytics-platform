"""``eap`` command-line interface.

Exposes the whole local pipeline as subcommands::

    eap ingest run
    eap spark run-all
    eap warehouse build
    eap quality validate
    eap pipeline           # ingest -> spark -> warehouse -> quality

Installed as the ``eap`` console script via pyproject.
"""

from __future__ import annotations

import typer

from eap.utils.logging import configure_logging, get_logger

app = typer.Typer(add_completion=False, help="Enterprise Analytics Platform CLI")
ingest_app = typer.Typer(help="Raw data acquisition & cleaning")
spark_app = typer.Typer(help="PySpark transformation jobs")
warehouse_app = typer.Typer(help="Star-schema warehouse")
quality_app = typer.Typer(help="Data-quality validation")
app.add_typer(ingest_app, name="ingest")
app.add_typer(spark_app, name="spark")
app.add_typer(warehouse_app, name="warehouse")
app.add_typer(quality_app, name="quality")

log = get_logger("eap.cli")


@app.callback()
def _root(verbose: bool = typer.Option(False, "--verbose", "-v", help="DEBUG logging")) -> None:
    configure_logging(level="DEBUG" if verbose else None)


# --------------------------- ingest ---------------------------
@ingest_app.command("download")
def ingest_download(force: bool = typer.Option(False, help="Re-download even if present")) -> None:
    """Acquire the raw Olist CSVs into data/raw."""
    from eap.ingestion import download

    download(force=force)


@ingest_app.command("run")
def ingest_run(
    table: str = typer.Option("", help="Ingest a single table (default: all)"),
    skip_download: bool = typer.Option(False, help="Assume raw files already present"),
) -> None:
    """Download (unless skipped) then ingest into cleaned Parquet."""
    from eap.ingestion import download, ingest_all, ingest_one

    if not skip_download:
        download()
    if table:
        ingest_one(table)
    else:
        ingest_all()


# --------------------------- spark ---------------------------
@spark_app.command("run-all")
def spark_run_all() -> None:
    """Run every PySpark job (CSV -> partitioned Parquet)."""
    import sys
    from pathlib import Path

    # `spark_jobs` lives at the repo root, not under src/, so the installed
    # console script (whose sys.path[0] is its own Scripts/ dir) can't see it
    # unless we add the repo root explicitly.
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        from spark_jobs.run_all import main as run_all_main
    except Exception as exc:  # pragma: no cover
        log.error("spark.import_failed", error=str(exc))
        raise typer.Exit(code=1) from exc
    run_all_main()


# --------------------------- warehouse ---------------------------
@warehouse_app.command("build")
def warehouse_build() -> None:
    """Build the DuckDB star schema from processed Parquet."""
    from eap.warehouse import build_warehouse

    path = build_warehouse()
    typer.echo(f"Warehouse built at: {path}")


# --------------------------- quality ---------------------------
@quality_app.command("validate")
def quality_validate(
    table: str = typer.Option("", help="Validate a single table (default: all)"),
) -> None:
    """Run data-quality checks; exit non-zero if any fail."""
    from eap.quality import validate_all, validate_table

    report = validate_table(table) if table else validate_all()
    summary = report.summary()
    typer.echo(f"Quality: {summary}")
    if not report.success:
        for f in report.failed:
            typer.echo(f"  FAIL {f.table}.{f.check}: {f.detail}")
        raise typer.Exit(code=1)


# --------------------------- pipeline ---------------------------
@app.command("pipeline")
def pipeline(skip_download: bool = typer.Option(False, help="Skip the download step")) -> None:
    """Run the full local pipeline end-to-end."""
    from eap.ingestion import download, ingest_all
    from eap.quality import validate_all
    from eap.warehouse import build_warehouse

    if not skip_download:
        download()
    ingest_all()
    build_warehouse()
    report = validate_all()
    if not report.success:
        raise typer.Exit(code=1)
    typer.echo("Pipeline complete.")


if __name__ == "__main__":  # pragma: no cover
    app()
