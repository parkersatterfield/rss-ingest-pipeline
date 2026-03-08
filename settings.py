from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass(slots=True)
class FeedConfig:
    name: str
    url: str
    enabled: bool = True


@dataclass(slots=True)
class AppConfig:
    feeds_file: Path
    feeds: list[FeedConfig]
    poll_interval_seconds: int
    max_items_per_feed: int
    max_llm_articles_per_cycle: int
    request_timeout_seconds: int
    ollama_base_url: str
    ollama_summary_model: str
    ollama_embedding_model: str
    ollama_embedding_dimensions: int
    ollama_timeout_seconds: int
    ollama_max_content_chars: int
    ollama_inter_request_delay_ms: int
    qdrant_url: str
    qdrant_collection: str


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def load_config() -> AppConfig:
    load_dotenv()
    feeds_path = Path(_env_str("FEEDS_FILE", "feeds.yaml"))
    feeds = load_feeds(feeds_path)

    return AppConfig(
        feeds_file=feeds_path,
        feeds=feeds,
        poll_interval_seconds=_env_int("POLL_INTERVAL_SECONDS", 600),
        max_items_per_feed=_env_int("MAX_ITEMS_PER_FEED", 20),
        max_llm_articles_per_cycle=_env_int("MAX_LLM_ARTICLES_PER_CYCLE", 30),
        request_timeout_seconds=_env_int("REQUEST_TIMEOUT_SECONDS", 30),
        ollama_base_url=_env_str("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_summary_model=_env_str("OLLAMA_SUMMARY_MODEL", "llama3.1:8b"),
        ollama_embedding_model=_env_str("OLLAMA_EMBEDDING_MODEL", "all-minilm"),
        ollama_embedding_dimensions=_env_int("OLLAMA_EMBEDDING_DIMENSIONS", 384),
        ollama_timeout_seconds=_env_int("OLLAMA_TIMEOUT_SECONDS", 120),
        ollama_max_content_chars=_env_int("OLLAMA_MAX_CONTENT_CHARS", 2000),
        ollama_inter_request_delay_ms=_env_int("OLLAMA_INTER_REQUEST_DELAY_MS", 200),
        qdrant_url=_env_str("QDRANT_URL", "http://localhost:6333"),
        qdrant_collection=_env_str("QDRANT_COLLECTION", "news-v1"),
    )


def load_feeds(path: Path) -> list[FeedConfig]:
    if not path.exists():
        raise FileNotFoundError(f"Feeds file not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_feeds = data.get("feeds", [])
    feeds: list[FeedConfig] = []

    for item in raw_feeds:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        enabled = bool(item.get("enabled", True))
        if name and url:
            feeds.append(FeedConfig(name=name, url=url, enabled=enabled))

    if not feeds:
        raise ValueError("No valid feeds found in feeds config")

    return feeds
