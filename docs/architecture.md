# Architecture

The platform is a layered ELT system: acquire → clean → transform → model → serve.
Every layer is independently runnable and tested; the whole flow is orchestrated
by Airflow and reproducible with `make pipeline`.

## System diagram

```mermaid
flowchart TB
    subgraph SOURCE["📥 Source"]
        K[Kaggle Olist Dataset<br/>9 CSV files]
    end

    subgraph INGEST["🧹 Ingestion — src/eap/ingestion"]
        DL[download.py<br/>Kaggle API / local zip]
        ING[ingest.py<br/>clean · dedupe · type<br/>pandas reference impl]
    end

    subgraph SPARK["⚡ Spark — spark_jobs/"]
        S1[csv_to_parquet.py<br/>schema-driven cleaning<br/>partitioned writes]
        S2[transformations.py<br/>broadcast joins<br/>fact_orders_enriched]
    end

    subgraph STORE["🗄 Storage"]
        RAW[(data/raw<br/>CSV)]
        PROC[(data/processed<br/>Parquet)]
        PQ[(data/parquet<br/>partitioned Parquet)]
        DUCK[(DuckDB<br/>olist.duckdb)]
        PG[(PostgreSQL<br/>olist schema)]
    end

    subgraph TRANSFORM["🔧 Transform"]
        WB[warehouse/build.py<br/>star schema builder]
        DBT[dbt — staging → intermediate → marts<br/>core / finance / marketing]
    end

    subgraph QUALITY["✅ Quality — src/eap/quality"]
        GE[validate.py + Great Expectations<br/>nulls · PK/FK · ranges]
    end

    subgraph ORCH["🗓 Orchestration"]
        AF[Airflow DAGs<br/>ingestion · pipeline · quality · reporting]
    end

    subgraph SERVE["📊 Serving"]
        API[FastAPI<br/>/kpis /revenue /customers<br/>/orders /products /dashboard]
        ST[Streamlit<br/>Overview · Analytics<br/>Customer Search · Forecast]
        PBI[Power BI / Excel<br/>via extracts + Postgres]
    end

    K --> DL --> RAW
    RAW --> ING --> PROC
    RAW --> S1 --> PQ --> S2 --> PQ
    PROC --> WB --> DUCK
    PROC --> DBT --> DUCK
    DUCK --> PG
    PROC --> GE
    AF -.orchestrates.-> INGEST & SPARK & TRANSFORM & QUALITY
    DUCK --> API
    DUCK --> ST
    PG --> PBI
```

## Layer responsibilities

| Layer | Code | Contract |
|---|---|---|
| Acquisition | `eap.ingestion.download` | Raw CSVs exist in `data/raw`; idempotent |
| Cleaning | `eap.ingestion.ingest` (pandas), `spark_jobs/csv_to_parquet` (Spark) | Typed, deduplicated Parquet; both driven by the same `catalog.py` |
| Modelling | `eap.warehouse.build` (deterministic baseline), `dbt/olist` (marts + tests) | Identical star-schema table names in DuckDB and Postgres |
| Quality | `eap.quality` | Fails the pipeline on null/PK/FK/range regressions |
| Orchestration | `airflow/dags` | Thin DAGs; logic stays in the tested package |
| Serving | `api/`, `streamlit/` | Read-only consumers of the warehouse |

## Key design decisions

1. **Single source of schema truth.** `src/eap/config/catalog.py` declares every
   table's keys, timestamps and numeric columns. Ingestion (pandas *and*
   Spark), validation and the warehouse builder all read it — schema knowledge
   lives in exactly one place.
2. **Dual warehouse, one schema.** DuckDB gives a zero-infrastructure local
   OLAP engine for the API, Streamlit and tests; Postgres is the "enterprise"
   target with full DDL, indexes, views and procedures. Table names are
   identical, so the 78-query SQL library runs on both.
3. **Thin orchestration.** Airflow tasks call the `eap` CLI / package. DAG
   files contain no business logic, which keeps them testable and diff-able.
4. **Quality as a gate, not a report.** `eap quality validate` exits non-zero
   on failure, so both `make pipeline` and the Airflow DAG stop before bad
   data reaches marts.

## ER diagram

See [er_diagram.md](er_diagram.md).
