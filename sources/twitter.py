from datetime import datetime, timezone

import httpx

from config import AI_QUERY, X_BEARER_TOKEN, window
from models import NewsItem

X_SEARCH = "https://api.twitter.com/2/tweets/search/recent"


def _ai_tweet_query(days: int) -> str:
    keywords = (
        "AI OR \"artificial intelligence\" OR \"machine learning\" OR "
        "LLM OR OpenAI OR Anthropic OR Claude OR Gemini OR GPT"
    )
    return f"({keywords}) -is:retweet lang:en"


def fetch_twitter(days: int) -> list[NewsItem]:
    if not X_BEARER_TOKEN:
        return []
    if days > 7:
        days = 7
    start, end = window(days)
    start_time = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    params = {
        "query": _ai_tweet_query(days),
        "max_results": 100,
        "start_time": start_time,
        "tweet.fields": "created_at,public_metrics,entities",
        "expansions": "author_id",
    }
    try:
        resp = httpx.get(X_SEARCH, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError:
        return []

    data = resp.json()
    tweets = {t["id"]: t for t in data.get("data", [])}
    items: list[NewsItem] = []
    for tid, tweet in tweets.items():
        metrics = tweet.get("public_metrics", {})
        engagement = (
            int(metrics.get("like_count", 0))
            + int(metrics.get("retweet_count", 0)) * 3
            + int(metrics.get("reply_count", 0)) * 2
            + int(metrics.get("quote_count", 0)) * 2
        )
        created_raw = tweet.get("created_at")
        if not created_raw:
            continue
        published = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        if not (start <= published <= end):
            continue
        text = tweet.get("text", "").strip()
        url = f"https://x.com/i/web/status/{tid}"
        items.append(
            NewsItem(
                title=text[:120] + ("…" if len(text) > 120 else ""),
                url=url,
                source="twitter",
                published=published,
                engagement=engagement,
                engagement_label=(
                    f"{metrics.get('like_count', 0)} likes · "
                    f"{metrics.get('retweet_count', 0)} RTs"
                ),
                summary=text[:280],
            )
        )
    return items
