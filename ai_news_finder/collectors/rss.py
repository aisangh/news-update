"""RSS feed collector — no API key required."""

import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import feedparser
import requests
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)

USER_AGENT = "AINewsFinder/1.0 (educational project)"
TIMEOUT = 10

# (display name, feed URL)
FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("ZDNet AI", "https://www.zdnet.com/topic/artificial-intelligence/rss.xml"),
    ("InfoQ AI", "https://feed.infoq.com/"),
]

GOOGLE_NEWS_QUERIES = [
    "artificial+intelligence",
    "OpenAI+OR+ChatGPT+OR+Claude+OR+Gemini",
    "machine+learning+OR+LLM",
]


def _google_news_url(query: str) -> str:
    q = quote_plus(query)
    return (
        f"https://news.google.com/rss/search?q={q}"
        "&hl=en-US&gl=US&ceid=US:en"
    )


def _fetch_feed(url: str) -> bytes | str | None:
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()
        return resp.content
    except Exception as exc:
        logger.warning("RSS fetch failed (%s): %s", url, exc)
        return None


def _parse_entry_date(entry: Any) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                dt = date_parser.parse(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                pass
    return None


def _entry_summary(entry: Any) -> str:
    raw = entry.get("summary") or entry.get("description") or ""
    return re.sub(r"<[^>]+>", "", raw).strip()


def _publisher_from_title(title: str) -> str | None:
    """Google News titles often end with ' - Publisher Name'."""
    m = re.search(r"\s[-–—|]\s+(.+?)\s*$", title)
    if m:
        pub = m.group(1).strip()
        if len(pub) > 2 and len(pub) < 80:
            return pub
    return None


def _source_label(feed_name: str, title: str) -> str:
    if feed_name.startswith("Google News"):
        publisher = _publisher_from_title(title)
        if publisher:
            return publisher
    return feed_name


def _parse_feed(source_name: str, feed_url: str, cutoff: datetime) -> list[dict]:
    raw = _fetch_feed(feed_url)
    if not raw:
        return []

    parsed = feedparser.parse(raw)
    if not parsed.entries:
        if getattr(parsed, "bozo", False):
            logger.warning(
                "RSS parse issue for %s: %s",
                source_name,
                getattr(parsed, "bozo_exception", "no entries"),
            )
        return []

    stories: list[dict] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not title or not url:
            continue

        pub = _parse_entry_date(entry)
        if pub and pub < cutoff:
            continue

        stories.append(
            {
                "title": title,
                "url": url,
                "source": _source_label(source_name, title),
                "summary": _entry_summary(entry),
                "date": pub.isoformat() if pub else None,
            }
        )
    return stories


def collect_rss(cutoff: datetime) -> list[dict]:
    """Pull stories from configured RSS feeds within the date window."""
    stories: list[dict] = []

    for source_name, feed_url in FEEDS:
        try:
            stories.extend(_parse_feed(source_name, feed_url, cutoff))
        except Exception as exc:
            logger.warning("RSS feed failed (%s): %s", source_name, exc)

    google_labels = ("Google News AI", "Google News LLM", "Google News OpenAI")
    for label, query in zip(google_labels, GOOGLE_NEWS_QUERIES):
        try:
            stories.extend(_parse_feed(label, _google_news_url(query), cutoff))
        except Exception as exc:
            logger.warning("Google News RSS failed (%s): %s", query, exc)

    return stories
