from datetime import datetime, timezone

import httpx

from config import REDDIT_SUBREDDITS, window
from models import NewsItem

REDDIT_BASE = "https://www.reddit.com"
HEADERS = {"User-Agent": "ai-news-agent/1.0 (research bot)"}


def _time_param(days: int) -> str:
    if days <= 1:
        return "day"
    if days <= 7:
        return "week"
    if days <= 30:
        return "month"
    return "year"


def fetch_reddit(days: int) -> list[NewsItem]:
    start, end = window(days)
    t = _time_param(days)
    items: list[NewsItem] = []
    for sub in REDDIT_SUBREDDITS:
        url = f"{REDDIT_BASE}/r/{sub}/top.json"
        params = {"t": t, "limit": 50}
        try:
            resp = httpx.get(url, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except httpx.HTTPError:
            continue
        for child in resp.json().get("data", {}).get("children", []):
            post = child.get("data", {})
            created = post.get("created_utc")
            if not created:
                continue
            published = datetime.fromtimestamp(created, tz=timezone.utc)
            if not (start <= published <= end):
                continue
            ups = int(post.get("ups") or 0)
            comments = int(post.get("num_comments") or 0)
            engagement = ups + comments * 2
            link = post.get("url") or ""
            if post.get("is_self"):
                link = f"{REDDIT_BASE}{post.get('permalink', '')}"
            if not link:
                continue
            items.append(
                NewsItem(
                    title=post.get("title", "").strip(),
                    url=link,
                    source="reddit",
                    published=published,
                    engagement=engagement,
                    engagement_label=f"{ups} upvotes · {comments} comments · r/{sub}",
                    summary=(post.get("selftext") or "")[:200],
                )
            )
    return items
