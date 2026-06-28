"""Selection logic — primary pool, secondary pool, Reddit fallback."""

from __future__ import annotations

from .dedup import _title_similarity

TOP_N = 10
DUPLICATE_THRESHOLD = 0.64

MAINSTREAM_SOURCE_BONUS = {
    "reuters": 70,
    "bbc": 60,
    "ap": 55,
    "associated press": 55,
    "techcrunch": 45,
    "the verge": 40,
    "wired": 40,
    "ars technica": 40,
    "mit tech review": 38,
    "venturebeat": 36,
    "zdnet": 30,
    "infoq": 28,
    "google news": 20,
}


def _story_titles(story: dict) -> list[str]:
    titles = [story.get("title") or "", *(story.get("all_titles") or [])]
    return [t for t in titles if t]


def _story_texts(story: dict) -> list[str]:
    texts = _story_titles(story)
    for key in ("summary", "detailed_summary"):
        if story.get(key):
            texts.append(story[key])
    texts.extend(story.get("all_summaries") or [])
    return [t[:500] for t in texts if t]


def _story_urls(story: dict) -> set[str]:
    return {u for u in [story.get("url") or "", *(story.get("all_urls") or [])] if u}


def _story_quality_score(story: dict) -> int:
    """Prefer stories with stronger sourcing and richer context."""
    source_count = int(story.get("source_count", 0) or 0)
    source_count = max(source_count, len([s for s in (story.get("sources") or []) if s]))
    summary = story.get("detailed_summary") or story.get("summary") or ""
    summary_words = len(summary.split())
    title_count = len([t for t in (story.get("all_titles") or []) if t])
    summary_count = len([s for s in (story.get("all_summaries") or []) if s])
    score = 0
    score += source_count * 120
    score += min(summary_words, 160)
    score += min(title_count, 8) * 8
    score += min(summary_count, 8) * 6
    if story.get("detailed_summary"):
        score += 40
    if story.get("read_more_links"):
        score += 25
    if not story.get("social_fallback"):
        score += 15
    if story.get("url") and not str(story.get("url")).startswith("https://news.google.com"):
        score += 10
    sources = " ".join(story.get("sources") or []).lower()
    for needle, bonus in MAINSTREAM_SOURCE_BONUS.items():
        if needle in sources:
            score += bonus
            break
    title = (story.get("title") or "").lower()
    high_signal_terms = (
        "openai",
        "anthropic",
        "claude",
        "gemini",
        "chatgpt",
        "reasoning model",
        "multimodal",
        "agent",
        "ai chip",
        "data center",
        "policy",
        "regulation",
        "safety",
        "robot",
        "robotics",
        "launch",
        "release",
    )
    if any(term in title for term in high_signal_terms):
        score += 12
    return score


def _is_duplicate_story(candidate: dict, selected: list[dict]) -> bool:
    candidate_urls = _story_urls(candidate)
    for existing in selected:
        if candidate_urls & _story_urls(existing):
            return True
        for cand_text in _story_texts(candidate):
            for existing_text in _story_texts(existing):
                if _title_similarity(cand_text, existing_text) >= DUPLICATE_THRESHOLD:
                    return True
    return False


def _append_unique_story(selected: list[dict], candidate: dict) -> bool:
    if _is_duplicate_story(candidate, selected):
        return False
    selected.append(dict(candidate))
    return True


def select_top_stories(
    groups: list[dict],
    reddit_stories: list[dict] | None = None,
    limit: int = TOP_N,
) -> tuple[list[dict], dict]:
    """
    Select up to limit stories using 3-step logic.
    Returns (selected_stories, stats_dict).
    """
    reddit_stories = reddit_stories or []

    primary = [g for g in groups if g.get("source_count", 0) >= 3]
    primary.sort(key=lambda g: (_story_quality_score(g), g.get("source_count", 0)), reverse=True)
    selected: list[dict] = []
    for item in primary:
        _append_unique_story(selected, item)
        if len(selected) >= limit:
            break

    secondary_added = 0
    if len(selected) < limit:
        secondary = [g for g in groups if g.get("source_count", 0) < 3]
        secondary.sort(key=lambda g: (_story_quality_score(g), g.get("source_count", 0)), reverse=True)
        for g in secondary:
            if _append_unique_story(selected, g):
                secondary_added += 1
            if len(selected) >= limit:
                break

    reddit_added = 0
    if len(selected) < limit:
        for post in reddit_stories:
            post_date = post.get("date")
            item = {
                "title": post.get("title") or "",
                "url": post.get("url") or "",
                "sources": [post.get("source") or "Reddit"],
                "source_count": 1,
                "summary": post.get("summary") or "",
                "date": post_date,
                "first_published": post_date,
                "all_urls": [post.get("url") or ""],
                "source_homes": [post.get("source_home") or ""],
                "all_titles": [post.get("title") or ""],
                "all_summaries": [post.get("summary") or ""] if post.get("summary") else [],
                "social_fallback": "reddit",
            }
            if _append_unique_story(selected, item):
                reddit_added += 1
            if len(selected) >= limit:
                break

    for i, item in enumerate(selected):
        item["rank"] = i + 1

    stats = {
        "primary_count": min(len(primary), limit),
        "secondary_added": secondary_added,
        "reddit_added": reddit_added,
        "total_groups": len(groups),
    }
    return selected, stats
