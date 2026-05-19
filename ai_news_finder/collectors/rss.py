"""RSS feed collector — no API key required."""

from __future__ import annotations

import logging
import html
import re
from datetime import datetime, timezone
from functools import lru_cache
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse

import feedparser
import requests
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)

USER_AGENT = "AINewsFinder/1.0 (educational project)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
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
        self.paragraphs: list[str] = []
        self._capture_paragraph = False
        self._paragraph_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        if tag_name == "meta":
            attr_map = {k.lower(): v or "" for k, v in attrs}
            key = (attr_map.get("property") or attr_map.get("name") or "").lower()
            if key in {"description", "og:description", "twitter:description"}:
                self.candidates.append(attr_map.get("content", ""))
        elif tag_name == "p":
            self._capture_paragraph = True
            self._paragraph_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "p" or not self._capture_paragraph:
            return
        text = _clean_feed_text(" ".join(self._paragraph_parts))
        if len(text.split()) >= 12:
            self.paragraphs.append(text)
        self._capture_paragraph = False
        self._paragraph_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_paragraph:
            self._paragraph_parts.append(data)


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
    text = re.sub(r"\bBy [A-Z][A-Za-z .'-]{2,80}$", "", text).strip()
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


def _is_redirect_url(url: str) -> bool:
    host = urlparse(url or "").netloc.lower()
    return "news.google.com" in host or "feedproxy" in host


def _sentence_split(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _keywords(text: str) -> set[str]:
    stopwords = {
        "about", "after", "again", "against", "also", "amid", "among", "and",
        "are", "artificial", "because", "been", "being", "but", "can", "could",
        "from", "has", "have", "how", "into", "its", "machine", "more", "new",
        "not", "said", "says", "that", "the", "their", "this", "through", "was",
        "were", "what", "when", "where", "which", "while", "will", "with",
        "using", "real", "time", "improves", "announces", "brings",
    }
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", text.lower())
    return {w for w in words if w not in stopwords}


def _article_sentence_score(sentence: str, title_keywords: set[str], seen: set[str]) -> int:
    words = sentence.split()
    if len(words) < 10 or len(words) > 55:
        return -100
    lower = sentence.lower()
    noisy_phrases = (
        "subscribe", "newsletter", "cookie", "advertisement", "sign up",
        "live updates", "seems to be getting", "click here", "read our",
    )
    if any(bad in lower for bad in noisy_phrases) or "…" in sentence:
        return -100
    overlap_terms = _keywords(sentence) & title_keywords
    weak_terms = {"code", "model", "models", "agent", "agents", "using", "real", "time"}
    kw_overlap = len(overlap_terms)
    if title_keywords and (kw_overlap == 0 or overlap_terms <= weak_terms):
        return -100
    novelty = len(_keywords(sentence) - seen)
    return (kw_overlap * 5) + min(novelty, 12) + min(len(words), 35)


def _build_detailed_summary(title: str, snippets: list[str]) -> str:
    title_keywords = _keywords(title)
    sentences: list[tuple[int, str]] = []
    for snippet in snippets:
        for sentence in _sentence_split(snippet):
            sentences.append((_article_sentence_score(sentence, title_keywords, set()), sentence))

    chosen: list[str] = []
    seen_keywords: set[str] = set()
    for initial_score, sentence in sentences:
        if len(chosen) >= 5:
            break
        clean = _clean_feed_text(sentence)
        score = _article_sentence_score(clean, title_keywords, seen_keywords)
        if initial_score < 0 or score < 18:
            continue
        if not clean or clean in chosen or _looks_weak_summary(clean, title):
            continue
        if any(clean.lower() in existing.lower() or existing.lower() in clean.lower() for existing in chosen):
            continue
        chosen.append(clean)
        seen_keywords.update(_keywords(clean))

    if len(chosen) < 3:
        ranked = sorted(sentences, key=lambda item: item[0], reverse=True)
        for _, sentence in ranked:
            if len(chosen) >= 5:
                break
            clean = _clean_feed_text(sentence)
            if not clean or clean in chosen or _looks_weak_summary(clean, title):
                continue
            if _article_sentence_score(clean, title_keywords, seen_keywords) < 18:
                continue
            chosen.append(clean)
            seen_keywords.update(_keywords(clean))

    if not chosen:
        return ""

    summary = " ".join(chosen)
    words = summary.split()
    if len(words) > 180:
        summary = " ".join(words[:180]).rsplit(" ", 1)[0].rstrip(",;:") + "..."
    return summary


def _best_article_summary(title: str, snippets: list[str]) -> str:
    """Choose the best usable article text when sentence extraction is sparse."""
    candidates = [_clean_feed_text(s) for s in snippets]
    candidates = [c for c in candidates if c and not _looks_weak_summary(c, title)]
    if not candidates:
        return ""
    return max(candidates, key=lambda c: min(len(c), 600))


def fetch_article_details(url: str, title: str = "") -> dict:
    """Fetch article metadata and paragraph text for richer reporting."""
    if not url or _is_redirect_url(url):
        return {}
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
        return {}

    parser = _MetaSummaryParser()
    try:
        parser.feed(resp.text[:200_000])
    except Exception:
        return {}

    candidates = [_clean_feed_text(c) for c in parser.candidates]
    meta_summaries = [c for c in candidates if c and not _looks_weak_summary(c, title)]
    paragraphs = [p for p in parser.paragraphs if p and not _looks_weak_summary(p, title)]
    detail_snippets = [*meta_summaries, *paragraphs[:12]]
    detailed_summary = _build_detailed_summary(title, detail_snippets)
    return {
        "url": resp.url,
        "meta_summary": max(meta_summaries, key=len) if meta_summaries else "",
        "detailed_summary": detailed_summary or _best_article_summary(title, detail_snippets),
        "paragraphs": paragraphs[:8],
    }


def fetch_article_summary(url: str, title: str = "") -> str:
    """Fetch a concise article summary from common HTML metadata."""
    details = fetch_article_details(url, title)
    return details.get("meta_summary") or details.get("detailed_summary") or ""


def _read_more_links(story: dict, limit: int = 2) -> list[dict[str, str]]:
    urls = [story.get("url") or "", *(story.get("all_urls") or [])]
    sources = story.get("sources") or []
    source_homes = story.get("source_homes") or []
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for idx, url in enumerate(urls):
        if not url or url in seen:
            continue
        seen.add(url)
        source = sources[idx] if idx < len(sources) else urlparse(url).netloc or "Article"
        source_home = source_homes[idx] if idx < len(source_homes) else (source_homes[0] if source_homes else "")
        article_url = discover_article_url(story.get("title") or "", source_home) if _is_redirect_url(url) else ""
        links.append({
            "url": article_url or url,
            "source": source,
            "original_url": url,
            "source_home": source_home,
        })
        if len(links) >= limit:
            break
    return links


def enrich_story_summaries(stories: list[dict]) -> None:
    """Improve selected stories with richer summaries and read-further links."""
    for story in stories:
        title = story.get("title") or ""
        story["read_more_links"] = _read_more_links(story, limit=2)
        detail_texts: list[str] = []

        for link in story["read_more_links"]:
            details = fetch_article_details(link["url"], title)
            if not details:
                continue
            final_url = details.get("url") or link["url"]
            if final_url:
                link["url"] = final_url
            for key in ("detailed_summary", "meta_summary"):
                value = details.get(key) or ""
                if value:
                    detail_texts.append(value)

        summaries = story.setdefault("all_summaries", [])
        for text in detail_texts:
            if text and text not in summaries:
                summaries.append(text)

        summary_pool = detail_texts if story["read_more_links"] else [*detail_texts, *summaries]
        detailed = _build_detailed_summary(title, summary_pool) or _best_article_summary(title, summary_pool)

        if detailed:
            story["detailed_summary"] = detailed
            story["summary"] = detailed
        elif _looks_weak_summary(story.get("summary") or "", title):
            fetched = fetch_article_summary(story.get("url") or "", title)
            if fetched:
                story["summary"] = fetched
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


def _entry_source_home(entry: Any) -> str:
    source = entry.get("source") or {}
    href = source.get("href") if isinstance(source, dict) else ""
    return href or ""


def _clean_title_for_search(title: str) -> str:
    cleaned = re.sub(r"\s(?:-|\|)\s+[^-|]{2,80}$", "", title).strip() or title
    cleaned = re.sub(r"[“”\"'’]", "", cleaned)
    cleaned = re.sub(r"[—–-]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _same_site(url: str, source_home: str) -> bool:
    candidate_host = urlparse(url or "").netloc.lower().removeprefix("www.")
    source_host = urlparse(source_home or "").netloc.lower().removeprefix("www.")
    return bool(candidate_host and source_host and (candidate_host == source_host or candidate_host.endswith("." + source_host)))


def _decode_ddg_href(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and "uddg=" in parsed.query:
        return parse_qs(parsed.query).get("uddg", [href])[0]
    return href


@lru_cache(maxsize=256)
def discover_article_url(title: str, source_home: str) -> str:
    """Find a publisher article URL when Google News only gives a wrapper link."""
    if not title or not source_home:
        return ""
    source_host = urlparse(source_home).netloc.lower().removeprefix("www.")
    if not source_host:
        return ""

    search_title = _clean_title_for_search(title)
    query = f"site:{source_host} {search_title}"
    try:
        resp = requests.get(
            "https://duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Article URL discovery failed (%s): %s", title, exc)
        return ""

    title_terms = _keywords(title)
    for match in re.finditer(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        resp.text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        href = _decode_ddg_href(html.unescape(match.group(1)))
        result_text = _clean_feed_text(match.group(2))
        if not href.startswith("http") or not _same_site(href, source_home):
            continue
        parsed = urlparse(href)
        if parsed.path in ("", "/"):
            continue
        overlap = _keywords(result_text) & title_terms
        result_terms = _keywords(result_text + " " + href)
        if len(overlap) >= 2 or len(result_terms & title_terms) >= 3 or search_title.lower() in result_text.lower():
            return href
    return ""


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
                "source_home": _entry_source_home(entry),
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
