from __future__ import annotations

import logging
from dataclasses import dataclass

from feed_ingest import fetch_articles
from models import VectorPoint
from ollama_client import OllamaClient
from qdrant_store import QdrantStore
from settings import AppConfig

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class CycleStats:
    fetched_articles: int = 0
    skipped_existing: int = 0
    summarized_articles: int = 0
    upserted_points: int = 0
    failed_articles: int = 0


class IngestPipeline:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._ollama = OllamaClient(config)
        self._qdrant = QdrantStore(config)

    def run_cycle(self) -> CycleStats:
        stats = CycleStats()
        records = fetch_articles(self._config)
        stats.fetched_articles = len(records)
        existing_ids = self._qdrant.get_existing_ids([record.id for record in records])
        stats.skipped_existing = len(existing_ids)

        vector_points: list[VectorPoint] = []
        llm_processed = 0

        for record in records:
            if record.id in existing_ids:
                continue
            if llm_processed >= self._config.max_llm_articles_per_cycle:
                LOGGER.info(
                    "Reached max LLM articles per cycle (%s), skipping remaining records",
                    self._config.max_llm_articles_per_cycle,
                )
                break
            try:
                summary = self._ollama.summarize(record.title, record.content)
                if not summary:
                    LOGGER.info("Skipping article with empty summary: %s", record.title)
                    continue

                vector = self._ollama.embed(summary)
                if not vector:
                    LOGGER.info(
                        "Skipping article with empty embedding: %s", record.title
                    )
                    continue
                if len(vector) != self._config.ollama_embedding_dimensions:
                    LOGGER.warning(
                        "Skipping article with unexpected embedding size for '%s': got=%s expected=%s",
                        record.title,
                        len(vector),
                        self._config.ollama_embedding_dimensions,
                    )
                    continue

                vector_points.append(
                    VectorPoint(
                        id=record.id,
                        title=record.title,
                        link=record.link,
                        summary=summary,
                        vector=vector,
                        published_date=record.published_date,
                    )
                )
                stats.summarized_articles += 1
                llm_processed += 1
            except Exception as exc:
                stats.failed_articles += 1
                LOGGER.warning("Failed to process article '%s': %s", record.title, exc)

        if vector_points:
            self._qdrant.ensure_collection()
            self._qdrant.upsert(vector_points)
            stats.upserted_points = len(vector_points)

        LOGGER.info(
            "Cycle complete | fetched=%s skipped_existing=%s summarized=%s upserted=%s failed=%s",
            stats.fetched_articles,
            stats.skipped_existing,
            stats.summarized_articles,
            stats.upserted_points,
            stats.failed_articles,
        )
        return stats
