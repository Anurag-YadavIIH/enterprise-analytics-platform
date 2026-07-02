# Docker

Three service-specific Dockerfiles, built and orchestrated by the root
[`docker-compose.yml`](../docker-compose.yml).

| Dockerfile | Base image | Installs | User | Port | Entrypoint |
|---|---|---|---|---|---|
| `Dockerfile.api` | `python:3.12-slim` | `eap[api]` (FastAPI + uvicorn) | non-root `appuser` | 8000 | `uvicorn api.main:app` |
| `Dockerfile.streamlit` | `python:3.12-slim` | `eap[app,ml]` (Streamlit, Plotly, Altair, scikit-learn, MLflow, statsmodels) | non-root `appuser` | 8501 | `streamlit run streamlit/app.py` |
| `Dockerfile.airflow` | `apache/airflow:2.9.1-python3.12` | `eap[quality]` + `dbt-core` + `dbt-duckdb` | image default (`airflow`) | 8080 | `airflow standalone` |

`docker-compose.yml` adds two more services around these three: **`postgres:16-alpine`**
(runs everything in `sql/ddl/` via `docker-entrypoint-initdb.d` on first boot, creating
the `olist` schema and star-schema tables) and **MLflow** (`ghcr.io/mlflow/mlflow`, tracking
server on :5000). Run the whole stack with `make up` (`docker compose up -d --build`) and
tear it down with `make down` (`docker compose down`, volumes kept).

## Notes from getting this running on real data

A few things needed fixing after these images were first built and are worth knowing about
if you touch them again:

- **API/Airflow host ports are overridable.** `docker-compose.yml` maps the API to
  `${API_HOST_PORT:-8000}:8000` and Airflow to `${AIRFLOW_HOST_PORT:-8080}:8080` so they
  can be remapped (e.g. `API_HOST_PORT=8001 docker compose up -d api`) without editing the
  file, in case those ports are already taken by something else on the host.
- **`Dockerfile.airflow` drops the base image's `mssql-release.list` apt source** before
  `apt-get update`. That source (`packages.microsoft.com`, for `mssql-tools`, which nothing
  here uses) has been observed serving a `Release` file with a future `Valid-From` timestamp
  on some CDN edges, which makes `apt-get update` fail outright with "not valid yet" even
  though nothing from that repo is actually needed.
- **`Dockerfile.airflow` re-pins `sqlalchemy` to `<2.0` after installing `eap`.** `eap`'s own
  dependencies require `sqlalchemy>=2.0`, which silently upgrades the environment past
  Airflow 2.9.1's own `sqlalchemy<2.0` requirement and crashes Airflow's ORM models
  (`TaskInstance`) at import time. The `eap[quality]` + `dbt-core`/`dbt-duckdb` install is
  followed by a forced `sqlalchemy>=1.4.36,<2.0` reinstall to keep Airflow bootable.
- The `api`/`streamlit` images read/write the app's `data/` directory via a bind mount
  (`./data:/app/data`); the app resolves that path relative to its current working directory
  (`WORKDIR /app`), not the package's install location, so it works whether `eap` was
  installed editable or not.
