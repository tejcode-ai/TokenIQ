# TokenIQ

TokenIQ is a small FastAPI backend for tracking AI API token usage, estimated or provider-reported costs, team and employee spend, budgets, spend spikes, and model cost comparisons.

## What is included

- REST API with interactive docs at `/docs`
- PostgreSQL support through SQLAlchemy and `psycopg`
- SQLite default for a quick local run when PostgreSQL is not installed
- Request-level usage ingestion and filters
- Cost calculation from a configurable per-model pricing catalog
- Company, team, and employee budgets with threshold status
- Simple daily spend spike detection
- Cost-only model comparison for recent token volume
- Sample usage data and automated API tests

This is a learning MVP. It does not include authentication, authorization, durable notification delivery, model-quality evaluation, or provider-specific usage synchronization. Do not expose it publicly with real company data until authentication and access controls are implemented. API providers change prices; update the catalog to match the applicable pricing and date before relying on cost estimates.

## Run locally

Use Python 3.10 or newer.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The default database is `sqlite:///./tokeniq.db`. The application creates tables and seeds example OpenAI and Anthropic model prices when it starts.

## Use PostgreSQL

Create a database and user in PostgreSQL, then set `DATABASE_URL` before starting the API. Copy `.env.example` as a reference; the app does not automatically load `.env`.

```powershell
$env:DATABASE_URL = "postgresql+psycopg://tokeniq:your-password@localhost:5432/tokeniq"
uvicorn app.main:app --reload
```

Tables are created at application startup for this prototype. A production deployment should use database migrations and a secret manager for credentials.

## Load sample usage

In another terminal with the same database configuration:

```powershell
python -m scripts.load_sample_data
```

Open `http://127.0.0.1:8000/docs` to explore the API.

## Main endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/usage` | Record usage and estimate cost or store a provider-reported cost |
| `GET` | `/api/v1/usage` | Filter usage by date, employee, team, or model |
| `GET` | `/api/v1/usage/summary` | Aggregate request, token, and cost totals |
| `GET` | `/api/v1/usage/breakdown?by=team` | Group totals by `employee`, `team`, or `model` |
| `POST` | `/api/v1/budgets` | Create a weekly or monthly spending limit |
| `GET` | `/api/v1/budgets/status` | Show spend, threshold alerts, and over-limit state |
| `GET` | `/api/v1/anomalies` | Compare daily costs with the preceding observed days |
| `GET` | `/api/v1/models/compare` | Compare estimated cost for the observed token mix |
| `GET/POST` | `/api/v1/models/pricing` | List or update model pricing |

For usage imports, set `reported_cost_usd` when the provider's record includes a cost. Otherwise the API calculates an estimate from the current catalog. Employee and team attribution must be supplied by your own application or mapping; provider usage exports do not necessarily include it.

Model comparison is strictly a price comparison using the same input/output token counts. It does not claim that models are interchangeable or recommend a model based on quality, safety, latency, or feature support.

## Test

```powershell
pytest
```

Tests use an isolated in-memory SQLite database and do not require a running PostgreSQL server.

## Suggested next step: real provider data

Start by exporting provider usage/cost reports and mapping each provider row into the `POST /api/v1/usage` format. Provider APIs and organization billing exports differ, so add a provider-specific importer only after choosing the source and confirming its available attribution fields. Keep API keys out of source code; use environment variables or a secret manager.
