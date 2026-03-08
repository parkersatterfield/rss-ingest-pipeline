from __future__ import annotations

import logging
from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from models import VectorPoint
from settings import AppConfig

LOGGER = logging.getLogger(__name__)


class QdrantStore:
    def __init__(self, config: AppConfig) -> None:
        self._collection = config.qdrant_collection
        self._distance = Distance.EUCLID
        self._vector_size = config.ollama_embedding_dimensions
        self._client = QdrantClient(url=config.qdrant_url)
        self._is_ready = False

    def ensure_collection(self) -> None:
        if self._is_ready:
            return

        collections = self._client.get_collections().collections
        exists = any(item.name == self._collection for item in collections)

        if not exists:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=self._vector_size, distance=self._distance
                ),
            )
            LOGGER.info(
                "Created Qdrant collection %s with vector size %s",
                self._collection,
                self._vector_size,
            )
        else:
            collection_info = self._client.get_collection(self._collection)
            vectors_config = collection_info.config.params.vectors
            existing_size = getattr(vectors_config, "size", None)
            existing_distance = getattr(vectors_config, "distance", None)
            if (
                existing_size != self._vector_size
                or existing_distance != self._distance
            ):
                raise RuntimeError(
                    "Existing collection configuration does not match required settings: "
                    f"required size={self._vector_size}, distance={self._distance}; "
                    f"found size={existing_size}, distance={existing_distance}."
                )

        # Datetime index supports fast range filtering for recency-based retrieval.
        self._client.create_payload_index(
            collection_name=self._collection,
            field_name="published_date",
            field_schema=PayloadSchemaType.DATETIME,
            wait=True,
        )
        self._is_ready = True

    def upsert(self, points: list[VectorPoint]) -> None:
        if not points:
            return
        if not self._is_ready:
            raise RuntimeError(
                "Collection not initialized. Call ensure_collection first."
            )

        payload_points: list[PointStruct] = []
        for point in points:
            published = point.published_date or datetime.now(tz=timezone.utc)
            payload = {
                "title": point.title,
                "link": point.link,
                "summary": point.summary,
                "published_date": published.isoformat(),
            }
            payload_points.append(
                PointStruct(
                    id=point.id,
                    vector=point.vector,
                    payload=payload,
                )
            )

        self._client.upsert(
            collection_name=self._collection, points=payload_points, wait=True
        )
        LOGGER.info(
            "Upserted %s points to collection %s", len(payload_points), self._collection
        )

    def get_existing_ids(self, ids: list[int], batch_size: int = 256) -> set[int]:
        if not ids:
            return set()

        collections = self._client.get_collections().collections
        exists = any(item.name == self._collection for item in collections)
        if not exists:
            return set()

        existing: set[int] = set()
        for start in range(0, len(ids), batch_size):
            chunk = ids[start : start + batch_size]
            points = self._client.retrieve(collection_name=self._collection, ids=chunk)
            for point in points:
                point_id = point.id
                if isinstance(point_id, int):
                    existing.add(point_id)

        return existing
