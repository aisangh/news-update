from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import httpx

from config import AI_QUERY, window
from models import NewsItem

GOOGLE_RSS = "https://news.google.com/rss/search"


def _parse_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
    return None


def _in_window(published: datetime | None, start: datetime, end: datetime) -> bool:
    if published is None:
        return False
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return start <= published <= end


def _fetch_rss(query: str, days: int, label: str) -> list[NewsItem]:
    start, end = window(days)
    after = start.strftime("%Y-%m-%d")
    before = end.strftime("%Y-%m-%d")
    q = f"{query} after:{after} before:{before}"
    url = (
        f"{GOOGLE_RSS}?q={quote_plus(q)}"
        "&hl=en-US&gl=US&ceid=US:en"
    )
    resp = httpx.get(url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    feed = feedparser.parse(resp.text)
    items: list[NewsItem] = []
    for entry in feed.entries:
        published = _parse_date(entry)
        if not _in_window(published, start, end):
            continue
        link = entry.get("link", "")
        if not link:
            continue
        items.append(
            NewsItem(
                title=entry.get("title", "").strip(),
                url=link,
                source=label,
                published=published,
                summary=entry.get("summary", "")[:280],
            )
        )
    return items


def fetch_google_news(days: int) -> list[NewsItem]:
    web = _fetch_rss(AI_QUERY, days, "google_news")
    twitter_q = f"{AI_QUERY} (site:x.com OR site:twitter.com)"
    social = _fetch_rss(twitter_q, days, "google_twitter")
    return web + social
