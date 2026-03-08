from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..config import load_config
from ..query.service import (
    ArticleQueryService,
    parse_iso_datetime,
    result_to_dict,
    results_to_dict,
)

mcp = FastMCP("rss-query-mcp")
_service = ArticleQueryService(load_config())


def run() -> None:
    mcp.run()


@mcp.tool()
def search_articles(
    keyword: str = "",
    published_from: str = "",
    published_to: str = "",
    limit: int = 20,
    scan_limit: int = 500,
) -> dict[str, object]:
    """Search ingested RSS articles by keyword and optional published date range.

    Args:
        keyword: Case-insensitive keyword to match in title or summary.
        published_from: ISO datetime lower bound (for example: 2026-03-01T00:00:00Z).
        published_to: ISO datetime upper bound (for example: 2026-03-08T23:59:59Z).
        limit: Max records returned (1-100).
        scan_limit: Max records scanned in Qdrant before keyword filtering (1-5000).
    """
    results = _service.search(
        keyword=keyword,
        published_from=parse_iso_datetime(published_from),
        published_to=parse_iso_datetime(published_to),
        limit=limit,
        scan_limit=scan_limit,
    )
    return {
        "count": len(results),
        "results": results_to_dict(results),
    }


@mcp.tool()
def get_article_by_id(article_id: int) -> dict[str, object]:
    """Get one ingested RSS article by deterministic Qdrant point ID."""
    result = _service.get_by_id(article_id)
    if not result:
        return {
            "found": False,
            "article": None,
        }

    return {
        "found": True,
        "article": result_to_dict(result),
    }


@mcp.tool()
def recent_articles(
    limit: int = 20,
    published_from: str = "",
    published_to: str = "",
    scan_limit: int = 1000,
) -> dict[str, object]:
    """Get recent ingested RSS articles with optional published date range filtering.

    Args:
        limit: Max records returned (1-100).
        published_from: ISO datetime lower bound.
        published_to: ISO datetime upper bound.
        scan_limit: Max records scanned in Qdrant before sorting by published date.
    """
    results = _service.recent(
        limit=limit,
        published_from=parse_iso_datetime(published_from),
        published_to=parse_iso_datetime(published_to),
        scan_limit=scan_limit,
    )
    return {
        "count": len(results),
        "results": results_to_dict(results),
    }


if __name__ == "__main__":
    run()
