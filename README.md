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

- `feed_ingest.py`: pulls and normalizes RSS entries.
- `ollama_client.py`: local model calls for summary and embedding.
- `qdrant_store.py`: collection creation, date indexing, upserts.
- `pipeline.py`: orchestrates one full ingest cycle.
- `main.py`: long-running loop (or one-shot mode).

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

### 5. Run pipeline

Run continuously:

```powershell
uv run python main.py
```

Run once:

```powershell
uv run python main.py --once
```

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
- `MAX_LLM_ARTICLES_PER_CYCLE`: max records sent to Ollama per cycle (default `12`)
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
