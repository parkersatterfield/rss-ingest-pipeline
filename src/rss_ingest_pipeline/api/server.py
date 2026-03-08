from __future__ import annotations

from fastapi import FastAPI, Query
import uvicorn

from ..config import load_config
from ..query.service import ArticleQueryService, parse_iso_datetime, results_to_dict

app = FastAPI(title="RSS Query API", version="0.1.0")
_service = ArticleQueryService(load_config())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search")
def search_articles(
    keyword: str | None = Query(
        default=None, description="Keyword to match in title or summary"
    ),
    published_from: str | None = Query(
        default=None, description="ISO datetime lower bound"
    ),
    published_to: str | None = Query(
        default=None, description="ISO datetime upper bound"
    ),
    limit: int = Query(default=20, ge=1, le=100),
    scan_limit: int = Query(default=500, ge=1, le=5000),
) -> dict[str, object]:
    from_dt = parse_iso_datetime(published_from)
    to_dt = parse_iso_datetime(published_to)

    results = _service.search(
        keyword=keyword,
        published_from=from_dt,
        published_to=to_dt,
        limit=limit,
        scan_limit=scan_limit,
    )

    return {
        "count": len(results),
        "results": results_to_dict(results),
    }


def run() -> None:
    uvicorn.run("rss_ingest_pipeline.api.server:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
