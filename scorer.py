import math
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from models import NewsItem

SOURCE_WEIGHT = {
    "reddit": 1.45,
    "google_viral": 1.4,
    "google_twitter": 1.35,
    "google_news": 1.2,
    "hacker_news": 0.85,
    "twitter": 1.3,
}

AI_MUST = re.compile(
    r"\b(ai\b|artificial intelligence|chatgpt|gpt-?4|gpt-?5|openai|claude|"
    r"gemini|anthropic|sora|robot|humanoid|generative|deepfake|copilot)\b",
    re.I,
)

VIRAL_KEYWORDS = re.compile(
    r"\b(viral|shocking|insane|crazy|banned|fired|robot|sora|deepfake|"
    r"replace jobs|billion|leak|scandal|video|demo|humanoid|mind.?blow)\b",
    re.I,
)

TECH_NOISE = re.compile(
    r"\b(arxiv|novel architecture|multi-omics|framework identifies|benchmark|"
    r"hyperparameter|fine-?tun|embedding|phd-?level)\b",
    re.I,
)


def _recency_boost(published: datetime | None, now: datetime) -> float:
    if not published:
        return 0.5
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age_hours = max((now - published).total_seconds() / 3600, 0.5)
    return 1.0 + 2.5 * math.exp(-age_hours / 48)


def _engagement_score(item: NewsItem) -> float:
    if item.engagement <= 0:
        return 0.0
    return math.log1p(item.engagement) * 12


def _title_signal(title: str) -> float:
    hits = len(VIRAL_KEYWORDS.findall(title))
    return min(hits * 3.0, 12.0)


def _cross_source_bonus(count: int) -> float:
    if count <= 1:
        return 0.0
    return (count - 1) * 8.0


def score_item(
    item: NewsItem,
    now: datetime,
    source_hits: int,
) -> float:
    blob = f"{item.title} {item.summary}"
    if not AI_MUST.search(blob):
        return -1.0
    if TECH_NOISE.search(blob) and not AI_MUST.search(item.title):
        return -1.0

    base = SOURCE_WEIGHT.get(item.source, 1.0)
    score = (
        _engagement_score(item) * base
        + _title_signal(item.title)
        + _recency_boost(item.published, now) * 5
        + _cross_source_bonus(source_hits)
    )
    host = urlparse(item.url).netloc.lower()
    if any(d in host for d in ("youtube.com", "v.redd.it", "tiktok.com", "instagram.com")):
        score += 18.0
    if any(d in host for d in ("nytimes.com", "theverge.com", "bbc.", "wired.com", "reuters.com")):
        score += 10.0
    if TECH_NOISE.search(blob):
        score -= 25.0
    return round(score, 2)


def merge_duplicates(items: list[NewsItem]) -> list[NewsItem]:
    by_key: dict[str, NewsItem] = {}
    key_sources: dict[str, set[str]] = {}

    for item in items:
        key = item.virality_key()
        if key not in by_key:
            by_key[key] = item
            key_sources[key] = {item.source}
            continue
        key_sources[key].add(item.source)
        existing = by_key[key]
        if item.engagement > existing.engagement:
            existing.engagement = item.engagement
            existing.engagement_label = item.engagement_label or existing.engagement_label
        if item.summary and not existing.summary:
            existing.summary = item.summary
        if item.published and (
            not existing.published or item.published > existing.published
        ):
            existing.published = item.published

    merged = list(by_key.values())
    for item in merged:
        item.tags = sorted(key_sources[item.virality_key()])
    return merged
