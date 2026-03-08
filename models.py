from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ArticleRecord:
    id: int
    title: str
    link: str
    published_date: datetime | None
    content: str
    feed_name: str
    feed_url: str


@dataclass(slots=True)
class VectorPoint:
    id: int
    title: str
    link: str
    summary: str
    vector: list[float]
    published_date: datetime | None
