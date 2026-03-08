---
description: "Use when building or modifying the Python RSS ingest pipeline, including feed configuration, summarization via local Ollama models, embedding generation, and Qdrant vector upserts."
applyTo: "**/*.py"
---
# RSS Ingest Pipeline Guidelines

## Architecture

- Build the system as a clear pipeline: `fetch -> normalize -> summarize -> embed -> upsert`.
- Keep components modular with small interfaces so feed ingestion, summarization, embedding, and vector storage can be swapped independently.
- Prefer explicit data contracts between stages (typed dicts, dataclasses, or Pydantic models).

## Feed Configuration

- Default feed subscriptions to `feeds.yaml` rather than hardcoding URLs.
- Treat feed identity and item identity as stable keys to support idempotent ingestion.
- Preserve source metadata (`feed_url`, `title`, `link`, `published_at`, `guid`) in normalized records.

## Local-First Model Usage

- Default to locally hosted Ollama endpoints for both summarization and embeddings.
- Keep model names configurable (for example via environment variables or config file).
- Keep prompts deterministic and concise for repeatable summaries.
- Default summary output to one compact paragraph (not bullet lists) unless a feed-specific override is configured.

## Qdrant Storage

- Use deterministic point IDs (for example hash of canonical item identity) to avoid duplicate vectors.
- Store both vectors and rich payload metadata so retrieval can show source context.
- Keep collection name, vector size, and distance metric configurable.

## Reliability and Operations

- Design ingestion to be safe to rerun without creating duplicate records.
- Add retry and timeout handling around network and model calls.
- Log pipeline progress at each stage with enough context to diagnose failed items.
- Isolate side effects so failed items can be retried independently.

## Python Practices

- Prefer type hints on public functions and pipeline models.
- Keep functions focused and testable; avoid large monolithic scripts.
- Use pathlib and structured configuration loading instead of ad hoc string paths.
- Separate pure transformation logic from I/O boundaries.
- Project uses uv for dependency and environment management.
