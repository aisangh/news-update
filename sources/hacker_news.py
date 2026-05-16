from datetime import datetime, timezone

import httpx

from config import HN_QUERY, window_epoch
from models import NewsItem

HN_API = "https://hn.algolia.com/api/v1/search"


def fetch_hacker_news(days: int) -> list[NewsItem]:
    since = window_epoch(days)
    params = {
        "query": HN_QUERY,
        "tags": "story",
        "numericFilters": f"created_at_i>{since}",
        "hitsPerPage": 100,
    }
    resp = httpx.get(HN_API, params=params, timeout=30)
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    items: list[NewsItem] = []
    for hit in hits:
        points = int(hit.get("points") or 0)
        comments = int(hit.get("num_comments") or 0)
        engagement = points + comments * 2
        ts = hit.get("created_at_i")
        published = (
            datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
        )
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        items.append(
            NewsItem(
                title=hit.get("title", "").strip(),
                url=url,
                source="hacker_news",
                published=published,
                engagement=engagement,
                engagement_label=f"{points} pts · {comments} comments",
            )
        )
    return items
