from __future__ import annotations

import logging
import time

import httpx

from ..config import AppConfig

LOGGER = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, config: AppConfig) -> None:
        self._base_url = config.ollama_base_url.rstrip("/")
        self._summary_model = config.ollama_summary_model
        self._embedding_model = config.ollama_embedding_model
        self._timeout = config.ollama_timeout_seconds
        self._max_content_chars = config.ollama_max_content_chars
        self._inter_request_delay_seconds = max(
            0.0, config.ollama_inter_request_delay_ms / 1000
        )

    def summarize(self, title: str, content: str) -> str:
        source_text = (content or title).strip()
        if not source_text:
            return ""
        source_text = source_text[: self._max_content_chars]

        prompt = (
            "You are summarizing news for OSINT and journalism workflows. "
            "Write a factual summary in 2 to 4 sentences. "
            "Do not speculate and do not use bullet points.\n\n"
            f"Title: {title}\n"
            f"Content: {source_text}\n\n"
            "Summary:"
        )

        payload = {
            "model": self._summary_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 160,
                "num_ctx": 1024,
            },
        }
        response = self._post_with_retry("/api/generate", payload)
        self._sleep_between_requests()
        return str(response.get("response", "")).strip()

    def embed(self, text: str) -> list[float]:
        payload = {
            "model": self._embedding_model,
            "prompt": text,
        }
        response = self._post_with_retry("/api/embeddings", payload)
        self._sleep_between_requests()
        embedding = response.get("embedding", [])
        if not isinstance(embedding, list):
            return []
        return [float(value) for value in embedding]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = {
            "model": self._embedding_model,
            "input": texts,
        }

        try:
            response = self._post_with_retry("/api/embed", payload)
            self._sleep_between_requests()
            embeddings = response.get("embeddings", [])
            if not isinstance(embeddings, list):
                return []

            normalized: list[list[float]] = []
            for item in embeddings:
                if not isinstance(item, list):
                    normalized.append([])
                    continue
                normalized.append([float(value) for value in item])
            return normalized
        except Exception as exc:
            # Fallback for older Ollama builds that do not support /api/embed.
            LOGGER.warning(
                "Batch embedding endpoint unavailable; falling back to per-item embedding: %s",
                exc,
            )
            return [self.embed(text) for text in texts]

    def _post_with_retry(self, endpoint: str, payload: dict, attempts: int = 3) -> dict:
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(f"{self._base_url}{endpoint}", json=payload)
                    response.raise_for_status()
                    return response.json()
            except Exception as exc:
                last_error = exc
                LOGGER.warning(
                    "Ollama call failed (attempt %s/%s): %s", attempt, attempts, exc
                )
                time.sleep(0.5 * attempt)

        raise RuntimeError(
            f"Ollama request failed after {attempts} attempts: {last_error}"
        )

    def _sleep_between_requests(self) -> None:
        if self._inter_request_delay_seconds > 0:
            time.sleep(self._inter_request_delay_seconds)
