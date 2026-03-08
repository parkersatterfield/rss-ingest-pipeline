# rss-ingest-pipeline

Always-on Python pipeline that ingests configurable RSS feeds, generates concise local summaries with Ollama, creates vectors from those summaries, and upserts lean points into Qdrant.

## Goals

- Continuously collect global news and OSINT-oriented content.
- Keep feed subscriptions easy to add or remove via config.
- Store lean Qdrant points with these fields:
	- `id` (deterministic for dedup/upserts, includes feed identity + published date)
	- `title`
	- `link`
	- `summary` (2-4 sentence compact paragraph)
	- `vector` (generated from `summary`)
	- `published_date` (indexed in Qdrant for date filtering)

## Architecture

`fetch -> normalize -> summarize -> embed -> upsert`

Core code now lives under `src/rss_ingest_pipeline/`:

- `src/rss_ingest_pipeline/config.py`: environment + feed config loading.
- `src/rss_ingest_pipeline/models.py`: shared data models.
- `src/rss_ingest_pipeline/ingest/feed_ingest.py`: RSS fetch and normalization.
- `src/rss_ingest_pipeline/ingest/ollama_client.py`: summary and embedding calls.
- `src/rss_ingest_pipeline/ingest/qdrant_store.py`: Qdrant setup and upserts.
- `src/rss_ingest_pipeline/ingest/pipeline.py`: full ingest cycle orchestration.
- `src/rss_ingest_pipeline/ingest/cli.py`: ingest CLI entrypoint.
- `src/rss_ingest_pipeline/query/service.py`: keyword/date query service.
- `src/rss_ingest_pipeline/api/server.py`: FastAPI server.
- `src/rss_ingest_pipeline/mcp/server.py`: MCP server and tool definitions.

## Quick Start

### 1. Install dependencies

```powershell
uv sync
```

### 2. Start local Qdrant + Ollama

```powershell
docker compose up -d qdrant ollama
```

### 3. Pull Ollama models

```powershell
docker compose run --rm ollama-init
```

### 4. Configure environment

Copy `.env.example` to `.env` and adjust values if needed.

### 5. Run Ingest Pipeline

Run continuously (recommended while API/MCP are running):

```powershell
uv run ingest --log-level INFO
```

Run one cycle only:

```powershell
uv run ingest --once --log-level INFO
```

## End-to-End Runbook

Use 3 terminals so the system stays live while you query it.

1. Terminal A: keep ingest running

```powershell
uv run ingest --log-level INFO
```

2. Terminal B: start query API

```powershell
uv run api
```

3. Terminal C: start MCP server (for LLM tool use)

```powershell
uv run mcp
```

4. Optional: if you only want to backfill first, run a one-shot cycle before starting API/MCP

```powershell
uv run ingest --once --log-level INFO
```

## Scripts

Project scripts are defined in `pyproject.toml`:

- `uv run ingest` -> runs `rss_ingest_pipeline.ingest.cli:main`
- `uv run api` -> runs the FastAPI server on `0.0.0.0:8000`
- `uv run mcp` -> runs the MCP server (stdio)

Common examples:

```powershell
uv run ingest --once --log-level INFO
uv run api
uv run mcp
```

## Verify Services

Pipeline health is visible in logs via `Cycle complete | fetched=... upserted=...`.

API checks:

```powershell
curl "http://localhost:8000/health"
curl "http://localhost:8000/search?keyword=cyber&published_from=2026-03-01T00:00:00Z&limit=10"
```

MCP check (from Python, same service layer used by MCP tools):

```powershell
uv run python -c "from rss_ingest_pipeline.config import load_config; from rss_ingest_pipeline.query.service import ArticleQueryService; svc=ArticleQueryService(load_config()); print(len(svc.recent(limit=3)))"
```

## Query API

Lightweight API for keyword and published-date filtering over Qdrant payloads.

Start server:

```powershell
uv run api
```

If startup fails, check whether port `8000` is already in use and retry with another port, for example `--port 8001`.

Example query:

```powershell
curl "http://localhost:8000/search?keyword=cyber&published_from=2026-03-01T00:00:00Z&limit=10"
```

Endpoints:

- `GET /health`
- `GET /search?keyword=...&published_from=...&published_to=...&limit=...&scan_limit=...`

## MCP Server

MCP server exposing the same article search as an LLM tool.

Start MCP server (stdio transport):

```powershell
uv run mcp
```

Available tool:

- `search_articles(keyword, published_from, published_to, limit, scan_limit)`
- `get_article_by_id(article_id)`
- `recent_articles(limit, published_from, published_to, scan_limit)`

## Feed Configuration

Feeds are configured in `feeds.yaml`:

```yaml
feeds:
	- name: Reuters World
		url: https://feeds.reuters.com/Reuters/worldNews
		enabled: true
```

Add/remove feeds by editing this file.

## Environment Variables

- `POLL_INTERVAL_SECONDS`: loop interval (default `300`)
- `MAX_ITEMS_PER_FEED`: max entries per feed per cycle (default `20`)
- `MAX_LLM_ARTICLES_PER_CYCLE`: max records sent to Ollama per cycle (default `30`)
- `REQUEST_TIMEOUT_SECONDS`: HTTP timeout for feed/model calls (default `20`)
- `FEEDS_FILE`: feed config path (default `feeds.yaml`)
- `OLLAMA_BASE_URL`: Ollama endpoint (default `http://localhost:11434`)
- `OLLAMA_SUMMARY_MODEL`: summarization model name
- `OLLAMA_EMBEDDING_MODEL`: embedding model name (default `all-minilm`)
- `OLLAMA_EMBEDDING_DIMENSIONS`: expected embedding size (default `384`)
- `OLLAMA_TIMEOUT_SECONDS`: Ollama API timeout for local inference (default `120`)
- `OLLAMA_MAX_CONTENT_CHARS`: max article chars sent to summarizer (default `2000`)
- `OLLAMA_INTER_REQUEST_DELAY_MS`: pause between Ollama calls to reduce local load (default `200`)
- `QDRANT_URL`: Qdrant endpoint (default `http://localhost:6333`)
- `QDRANT_COLLECTION`: collection name (default `news-v1`)

## Notes

- Point IDs are deterministic hashes from feed identity and published date to support idempotent upserts.
- The Qdrant payload is intentionally lean: `title`, `link`, `summary`, `published_date`.
- `published_date` payload index is created automatically for fast date-range filtering.
- Qdrant vectors are always configured with Euclidean distance.
- Embeddings are validated to match the configured dimension (default `384` for `all-minilm`).

## Docker Files

- `docker-compose.yml`: local infra for `qdrant` and `ollama`, plus one-shot `ollama-init` model pull.
- `Dockerfile`: optional container build for running the Python pipeline itself.
