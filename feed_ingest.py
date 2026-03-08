from __future__ import annotations

import hashlib
import html
import logging
import re
import time
from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from models import ArticleRecord
from settings import AppConfig, FeedConfig

LOGGER = logging.getLogger(__name__)
TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    cleaned = TAG_RE.sub(" ", text)
    cleaned = html.unescape(cleaned)
    return " ".join(cleaned.split())


def _parse_published(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _record_id(feed_url: str, identity: str, published_key: str) -> int:
    digest = hashlib.sha1(
        f"{feed_url}|{identity}|{published_key}".encode("utf-8"), usedforsecurity=False
    ).hexdigest()
    # Use a deterministic signed-safe integer for Qdrant point IDs.
    return int(digest[:16], 16) & 0x7FFF_FFFF_FFFF_FFFF


def _extract_content(entry: dict) -> str:
    content_items = entry.get("content") or []
    if content_items and isinstance(content_items, list):
        first = content_items[0]
        if isinstance(first, dict):
            value = str(first.get("value", ""))
            if value.strip():
                return _strip_html(value)

    summary = str(entry.get("summary", "")).strip()
    if summary:
        return _strip_html(summary)

    title = str(entry.get("title", "")).strip()
    return _strip_html(title)


def _fetch_feed(client: httpx.Client, feed: FeedConfig, attempts: int = 3) -> bytes:
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            response = client.get(feed.url, follow_redirects=True)
            response.raise_for_status()
            return response.content
        except Exception as exc:
            last_error = exc
            LOGGER.warning(
                "Feed fetch failed for %s (attempt %s/%s): %s",
                feed.url,
                attempt,
                attempts,
                exc,
            )
            time.sleep(0.5 * attempt)

    raise RuntimeError(f"Failed to fetch feed after {attempts} attempts: {last_error}")


def fetch_articles(config: AppConfig) -> list[ArticleRecord]:
    articles_by_id: dict[int, ArticleRecord] = {}
    enabled_feed_count = 0

    LOGGER.info(
        "Starting feed poll for %s configured feeds (enabled-only)",
        len(config.feeds),
    )

    with httpx.Client(timeout=config.request_timeout_seconds) as client:
        for feed in config.feeds:
            if not feed.enabled:
                LOGGER.debug("Skipping disabled feed %s (%s)", feed.name, feed.url)
                continue

            enabled_feed_count += 1

            try:
                content = _fetch_feed(client, feed)
                parsed = feedparser.parse(content)
            except Exception as exc:
                LOGGER.warning(
                    "Failed to fetch feed %s (%s): %s", feed.name, feed.url, exc
                )
                continue

            total_entries = len(parsed.entries)
            selected_entries = parsed.entries[: config.max_items_per_feed]
            LOGGER.info(
                "Polled feed '%s' | url=%s entries=%s selected=%s",
                feed.name,
                feed.url,
                total_entries,
                len(selected_entries),
            )

            for entry in selected_entries:
                title = str(entry.get("title", "")).strip()
                link = str(entry.get("link", "")).strip()
                published_raw = (
                    str(entry.get("published", "")).strip()
                    or str(entry.get("updated", "")).strip()
                )
                published_date = _parse_published(published_raw)
                guid = (
                    str(entry.get("id", "")).strip()
                    or str(entry.get("guid", "")).strip()
                )
                identity = guid or link or title

                if not identity:
                    continue

                record = ArticleRecord(
                    id=_record_id(
                        feed.url,
                        identity,
                        published_date.isoformat() if published_date else published_raw,
                    ),
                    title=title or "Untitled",
                    link=link,
                    published_date=published_date,
                    content=_extract_content(entry),
                    feed_name=feed.name,
                    feed_url=feed.url,
                )
                articles_by_id[record.id] = record

    records = list(articles_by_id.values())
    LOGGER.info(
        "Feed poll complete | enabled_feeds=%s unique_articles=%s",
        enabled_feed_count,
        len(records),
    )
    return records
