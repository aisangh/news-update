"""RSS feed collector — no API key required."""

from __future__ import annotations

import logging
import html
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
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


class _MetaSummaryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.candidates: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        attr_map = {k.lower(): v or "" for k, v in attrs}
        key = (attr_map.get("property") or attr_map.get("name") or "").lower()
        if key in {"description", "og:description", "twitter:description"}:
            self.candidates.append(attr_map.get("content", ""))


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


def _clean_feed_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(raw or ""))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\bContinue reading\b.*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\bRead more\b.*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\bThe post .+? appeared first on .+?\.$", "", text, flags=re.IGNORECASE).strip()
    return text


def _looks_weak_summary(summary: str, title: str) -> bool:
    clean = _clean_feed_text(summary)
    clean_title = _clean_feed_text(title)
    if not clean:
        return True
    if len(clean.split()) < 18:
        return True
    clean_l = re.sub(r"\s(?:-|\|)\s+[^-|]{2,80}$", "", clean).lower()
    title_l = re.sub(r"\s(?:-|\|)\s+[^-|]{2,80}$", "", clean_title).lower()
    return clean_l in title_l or title_l in clean_l


def fetch_article_summary(url: str, title: str = "") -> str:
    """Fetch a concise article summary from common HTML metadata."""
    if not url or "news.google.com" in url:
        return ""
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Article summary fetch failed (%s): %s", url, exc)
        return ""

    parser = _MetaSummaryParser()
    try:
        parser.feed(resp.text[:200_000])
    except Exception:
        return ""

    candidates = [_clean_feed_text(c) for c in parser.candidates]
    candidates = [c for c in candidates if c and not _looks_weak_summary(c, title)]
    if not candidates:
        return ""
    return max(candidates, key=len)


def enrich_story_summaries(stories: list[dict]) -> None:
    """Improve selected stories with article metadata when RSS snippets are thin."""
    for story in stories:
        title = story.get("title") or ""
        current = story.get("summary") or ""
        if not _looks_weak_summary(current, title):
            continue
        fetched = fetch_article_summary(story.get("url") or "", title)
        if not fetched:
            continue
        story["summary"] = fetched
        summaries = story.setdefault("all_summaries", [])
        if fetched not in summaries:
            summaries.append(fetched)


def _entry_summary(entry: Any) -> str:
    candidates: list[str] = []
    for key in ("summary", "description"):
        raw = entry.get(key) or ""
        if raw:
            candidates.append(_clean_feed_text(raw))

    for content in entry.get("content") or []:
        raw = content.get("value") if isinstance(content, dict) else ""
        if raw:
            candidates.append(_clean_feed_text(raw))

    candidates = [c for c in candidates if c]
    if not candidates:
        return ""
    return max(candidates, key=len)


def _publisher_from_title(title: str) -> str | None:
    """Google News titles often end with ' - Publisher Name'."""
    m = re.search(r"\s(?:-|\|)\s+(.+?)\s*$", title)
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
