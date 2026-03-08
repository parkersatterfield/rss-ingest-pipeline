from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import DatetimeRange, FieldCondition, Filter

from ..config import AppConfig


@dataclass(slots=True)
class ArticleSearchResult:
    id: int
    title: str
    link: str
    summary: str
    published_date: str


class ArticleQueryService:
    def __init__(self, config: AppConfig) -> None:
        self._client = QdrantClient(url=config.qdrant_url)
        self._collection = config.qdrant_collection

    def search(
        self,
        keyword: str | None = None,
        published_from: datetime | None = None,
        published_to: datetime | None = None,
        limit: int = 20,
        scan_limit: int = 500,
    ) -> list[ArticleSearchResult]:
        safe_limit = max(1, min(limit, 100))
        safe_scan_limit = max(safe_limit, min(scan_limit, 5000))

        qdrant_filter = self._build_filter(
            published_from=published_from,
            published_to=published_to,
        )

        points, _ = self._client.scroll(
            collection_name=self._collection,
            scroll_filter=qdrant_filter,
            with_payload=True,
            with_vectors=False,
            limit=safe_scan_limit,
        )

        normalized_keyword = (keyword or "").strip().lower()
        results: list[ArticleSearchResult] = []

        for point in points:
            if not isinstance(point.id, int):
                continue

            payload = point.payload or {}
            if not isinstance(payload, dict):
                continue

            title = str(payload.get("title", "")).strip()
            link = str(payload.get("link", "")).strip()
            summary = str(payload.get("summary", "")).strip()
            published_date = str(payload.get("published_date", "")).strip()

            if normalized_keyword:
                haystack = f"{title}\n{summary}".lower()
                if normalized_keyword not in haystack:
                    continue

            results.append(
                ArticleSearchResult(
                    id=point.id,
                    title=title,
                    link=link,
                    summary=summary,
                    published_date=published_date,
                )
            )

        results.sort(key=lambda item: item.published_date, reverse=True)
        return results[:safe_limit]

    def get_by_id(self, article_id: int) -> ArticleSearchResult | None:
        points = self._client.retrieve(
            collection_name=self._collection,
            ids=[article_id],
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            return None

        point = points[0]
        if not isinstance(point.id, int):
            return None

        payload = point.payload or {}
        if not isinstance(payload, dict):
            return None

        return ArticleSearchResult(
            id=point.id,
            title=str(payload.get("title", "")).strip(),
            link=str(payload.get("link", "")).strip(),
            summary=str(payload.get("summary", "")).strip(),
            published_date=str(payload.get("published_date", "")).strip(),
        )

    def recent(
        self,
        limit: int = 20,
        published_from: datetime | None = None,
        published_to: datetime | None = None,
        scan_limit: int = 1000,
    ) -> list[ArticleSearchResult]:
        return self.search(
            keyword=None,
            published_from=published_from,
            published_to=published_to,
            limit=limit,
            scan_limit=scan_limit,
        )

    def _build_filter(
        self,
        published_from: datetime | None,
        published_to: datetime | None,
    ) -> Filter | None:
        if not published_from and not published_to:
            return None

        dt_range = DatetimeRange(
            gte=published_from.isoformat() if published_from else None,
            lte=published_to.isoformat() if published_to else None,
        )

        return Filter(
            must=[
                FieldCondition(
                    key="published_date",
                    range=dt_range,
                )
            ]
        )


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    raw = value.strip()
    if not raw:
        return None

    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    return datetime.fromisoformat(raw)


def results_to_dict(results: list[ArticleSearchResult]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "title": item.title,
            "link": item.link,
            "summary": item.summary,
            "published_date": item.published_date,
        }
        for item in results
    ]


def result_to_dict(result: ArticleSearchResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "title": result.title,
        "link": result.link,
        "summary": result.summary,
        "published_date": result.published_date,
    }
