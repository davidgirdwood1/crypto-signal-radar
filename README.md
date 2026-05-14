# Crypto Signal Radar

A locally-runnable pipeline that ingests, classifies, and triages public crypto signals using Kafka, DeepSeek, and a React dashboard.

It ingests DEX Screener and CoinGecko data, publishes normalized events into Redpanda/Kafka, classifies each event with DeepSeek or a deterministic mock fallback, persists operational data in PostgreSQL, and displays the full pipeline in a React dashboard.


## Demo

![Crypto Signal Radar demo](/docs/crypto_signal_radar.gif)
The dashboard shows live classified crypto events, source counts, worker health, model runs, dead letters, and a clickable token risk board.


## Why I Built This

Crypto and meme coin feeds move quickly, but most dashboards flatten everything into raw lists, charts, or price movement. The goal was to build a locally-runnable system that treats each signal as an operational event: ingest it, normalize it, classify it, persist it, and surface it in a way that supports triage.

The project also gave me a practical way to demonstrate several backend and product skills together:

- Event-driven architecture using Kafka-compatible topics.
- Independent long-running workers for ingestion and classification.
- AI classification with provider fallback behavior.
- Database-backed observability through model runs, dead letters, and worker heartbeats.
- A dashboard designed for investigation rather than marketing.

## What It Does
- The pipeline follows a single path: Ingest → Normalize → Publish → Classify → Persist → Display.
- Polls DEX Screener boost/profile endpoints and CoinGecko trending coins.
- Normalizes each source into a shared raw event shape.
- Publishes raw events into Kafka topics.
- Classifies events with DeepSeek using an OpenAI-compatible chat completions API.
- Falls back to a deterministic local classifier if the model provider is unavailable or no API key is configured.
- Stores raw events, classifications, model metadata, dead letters, and worker heartbeats in PostgreSQL.
- Shows an operational dashboard with filters, risk scoring, worker health, source counts, and clickable token triage.

## Architecture

![Crypto Signal Radar architecture](./docs/architecture.png)


## Key Product Choices

- **Paused by default:** The dashboard starts static so users can inspect data without the feed moving underneath them.
- **Independent scroll regions:** The event feed and risk board scroll separately, which makes investigation easier.
- **Clickable risk board:** Selecting a token on the right scrolls directly to the matching event on the left.
- **Human-readable worker status:** Worker heartbeats are shown with readable labels and stale heartbeat detection.
- **Graceful AI fallback:** If DeepSeek fails, times out, or is not configured, the pipeline still produces a mock classification for demo continuity.

## Tech Stack

- Python 3.11, FastAPI, SQLAlchemy, psycopg
- Kafka-compatible broker in Docker using Redpanda
- PostgreSQL 16 in Docker
- Python workers using `kafka-python`
- DeepSeek via OpenAI-compatible chat completions
- React 19, Vite, plain CSS, lucide icons
- Kafka UI for local topic inspection
- Docker Compose for local orchestration

## Data Model

Core tables:

- `raw_events`: normalized source events before classification.
- `classified_events`: model output, risk score, sentiment, reasoning, and suggested action.
- `model_runs`: model metadata, latency, status, token usage, and errors.
- `worker_heartbeats`: worker liveness and recent status details.
- `dead_letters`: failed events and error messages.

## Kafka Topics

Each topic isolates a concern — raw ingestion, processed classification, and failure routing

- `crypto.dex.boosts.raw`
- `crypto.dex.profiles.raw`
- `crypto.coingecko.trending.raw`
- `crypto.events.classified`
- `crypto.events.deadletter`

## API Endpoints

- `GET /health`
- `GET /api/events/raw`
- `GET /api/events/classified`
- `GET /api/events/classified/{id}`
- `POST /api/events/{raw_event_id}/reprocess`
- `GET /api/stats/summary`
- `GET /api/stats/worker-heartbeats`
- `GET /api/stats/model-runs`
- `GET /api/dead-letters`
- `GET /api/tokens/risk-board`

## Run Locally

From the project root:

```bash
cp .env.example .env
# Edit your API key and model in .env
docker compose up --build
```

![Crypto Signal Radar docker containers](./docs/docker_running_containers.png)

Then open:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/health
- Kafka UI: http://localhost:8080

PostgreSQL is exposed on host port `5433` and persists inside the `postgres_data` Docker volume.

## Local Configuration

The app reads local settings from `.env`. `DATABASE_URL` can be set directly, but if it is empty or omitted, the backend and workers build the Postgres connection string from these fields:

```bash
POSTGRES_USER=crypto_user
POSTGRES_PASSWORD=crypto_password
POSTGRES_DB=crypto_signal_radar
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
```

Docker Compose also supports host port overrides:

```bash
POSTGRES_HOST_PORT=5433
KAFKA_HOST_PORT=9092
KAFKA_UI_PORT=8080
KAFKA_UI_BOOTSTRAP_SERVERS=kafka:9092
BACKEND_PORT=8000
FRONTEND_PORT=5173
VITE_API_BASE_URL=http://localhost:8000
```

Inside Docker, services should keep using container DNS names like `postgres` and `kafka`. If running the backend or workers directly on the host, use a host-reachable database URL, for example:

```bash
DATABASE_URL=postgresql+psycopg://crypto_user:crypto_password@localhost:5433/crypto_signal_radar
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

## DeepSeek Configuration

The DeepSeek key lives only in `.env`, which should not be committed.

```bash
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_REQUEST_TIMEOUT_SECONDS=12
DEEPSEEK_MAX_RETRIES=0
DEEPSEEK_FALLBACK_TO_MOCK_ON_ERROR=true
```

The worker calls:

```text
POST {DEEPSEEK_BASE_URL}/chat/completions
```

with an OpenAI-compatible request body.

## Mock Mode

If `DEEPSEEK_API_KEY` is empty, or the chat response times out, the AI worker does not crash. It uses a deterministic local classifier so the full pipeline still runs without paid API usage.

Mock runs are visible in `model_runs.status` as `mock`, and the raw model response includes `"mock_mode": true`.

## Dead Letters

Dead letters are created when the classifier fails to process a Kafka message. The worker stores the failed payload in PostgreSQL and also publishes a copy to `crypto.events.deadletter`.

In the dashboard, the **Dead letters** metric opens a modal when any failures exist. The modal shows the source topic, error message, retry count, timestamp, and payload JSON.

You can inspect recent dead letters directly in Postgres:

```sql
SELECT id, source_topic, error_message, retry_count, created_at, payload
FROM dead_letters
ORDER BY created_at DESC
LIMIT 25;
```

Or through the API:

```bash
curl http://localhost:8000/api/dead-letters
```

The project currently stores and displays dead letters, but does not yet replay them automatically. Manual reprocessing exists for raw events through:

```text
POST /api/events/{raw_event_id}/reprocess
```

## Public Data Sources

- DEX Screener latest boosts: `https://api.dexscreener.com/token-boosts/latest/v1`
- DEX Screener top boosts: `https://api.dexscreener.com/token-boosts/top/v1`
- DEX Screener latest profiles: `https://api.dexscreener.com/token-profiles/latest/v1`
- DEX Screener token enrichment: `https://api.dexscreener.com/tokens/v1/{chainId}/{tokenAddresses}`
- CoinGecko trending: `https://api.coingecko.com/api/v3/search/trending`

Data sources were chosen for global availability.

## Useful Commands

Start the full stack:

```bash
docker compose up --build
```

Start without rebuilding:

```bash
docker compose up -d
```

Rebuild a single service after code changes:

```bash
docker compose up -d --build frontend
docker compose up -d --build backend
docker compose up -d --build worker-ai-classifier
```

The frontend mounts `./frontend/src` into the container, so Vite may hot reload source-only edits. If the browser does not show a UI change after a hard refresh, rebuild the `frontend` service.

Pause live ingestion and classification:

```bash
docker compose stop worker-dex-producer worker-coingecko-producer worker-ai-classifier
```

Resume live ingestion and classification:

```bash
docker compose up -d worker-dex-producer worker-coingecko-producer worker-ai-classifier
```

Watch classifier logs:

```bash
docker compose logs -f worker-ai-classifier
```

Open Postgres:

```bash
docker compose exec postgres psql -U crypto_user -d crypto_signal_radar
```

Reset all local data:

```bash
docker compose down -v
```

## Design Decisions

- Local event-driven system instead of a simple dashboard that directly fetches APIs from the browser.
- Kafka topics isolate ingestion, classification, failure routing, and UI consumption, so each concern can evolve or fail independently.
- Different workers so source polling and AI classification can run at independent speeds.
- DeepSeek classification behind an OpenAI-compatible API boundary.
- Deterministic mock mode so demos still work when API keys are missing or provider calls fail.
- Store operational metadata for debugging: model latency, worker heartbeats, dead letters, and raw payloads.
- Dashboard optimized for triage: pause mode, independent scroll regions, filters, source counts, worker status, and click-to-focus risk board behavior.

## Tradeoffs

- The project uses Docker Compose and local volumes instead of managed infrastructure.
- There is no Alembic migration layer yet; schema is initialized through `db/init.sql`.
- Worker status is inferred from database heartbeats, not Docker APIs.
- The classifier prompt is intentionally compact to keep latency and cost low.
- The model output is validated, but a production system would need stronger review and escalation workflows.

## Future Improvements

- Add Alembic migrations for schema evolution.
- Add topic creation/init jobs for stricter Kafka setup.
- Add unit tests around normalization, prompt validation, and JSON parsing.
- Add historical charts for risk scores and classification distribution.
- Add more public data sources and social narrative inputs.
- Add manual review workflows for promoted, suspicious, or high-risk tokens.
- Add replay tooling for dead-lettered events.
- Add Docker health-based worker status in addition to heartbeat-based status.

---
*This project is for engineering portfolio and educational purposes only. Not financial advice.*