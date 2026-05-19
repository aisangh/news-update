"""Selection logic — primary pool, secondary pool, Reddit fallback."""

from __future__ import annotations

TOP_N = 10


def select_top_stories(
    groups: list[dict],
    reddit_stories: list[dict] | None = None,
) -> tuple[list[dict], dict]:
    """
    Select up to TOP_N stories using 3-step logic.
    Returns (selected_stories, stats_dict).
    """
    reddit_stories = reddit_stories or []

    primary = [g for g in groups if g.get("source_count", 0) >= 3]
    primary.sort(key=lambda g: g["source_count"], reverse=True)
    selected = primary[:TOP_N]

    secondary_added = 0
    if len(selected) < TOP_N:
        needed = TOP_N - len(selected)
        secondary = [g for g in groups if g.get("source_count", 0) < 3]
        secondary.sort(key=lambda g: g["source_count"], reverse=True)
        for g in secondary[:needed]:
            selected.append(dict(g))
            secondary_added += 1

    reddit_added = 0
    if len(selected) < TOP_N:
        needed = TOP_N - len(selected)
        for post in reddit_stories[:needed]:
            post_date = post.get("date")
            selected.append(
                {
                    "title": post.get("title") or "",
                    "url": post.get("url") or "",
                    "sources": [post.get("source") or "Reddit"],
                    "source_count": 1,
                    "summary": post.get("summary") or "",
                    "date": post_date,
                    "first_published": post_date,
                    "all_urls": [post.get("url") or ""],
                    "social_fallback": "reddit",
                }
            )
            reddit_added += 1

    for i, item in enumerate(selected):
        item["rank"] = i + 1

    stats = {
        "primary_count": min(len(primary), TOP_N),
        "secondary_added": secondary_added,
        "reddit_added": reddit_added,
        "total_groups": len(groups),
    }
    return selected, stats
