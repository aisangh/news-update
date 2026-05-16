#!/usr/bin/env python3
"""Stdlib-only AI news agent (no pip install required)."""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

AI_QUERY = (
    '("artificial intelligence" OR "machine learning" OR "large language model" '
    'OR LLM OR GPT OR Claude OR Gemini OR OpenAI OR Anthropic OR "AI model" '
    'OR "generative AI" OR AGI OR deep learning OR neural network)'
)
REDDIT_SUBS = ["MachineLearning", "artificial", "LocalLLaMA", "OpenAI", "singularity", "ChatGPT"]
HN_QUERY = "AI OR artificial intelligence OR machine learning OR LLM OR OpenAI OR Anthropic"
UA = "ai-news-agent/1.0"


def window(days: int):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return start, end


def fetch_url(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_rss(xml_bytes: bytes, start, end, source: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    channel = root.find("channel")
    if channel is None:
        channel = root
    items = []
    for entry in channel.findall("item"):
        title = (entry.findtext("title") or "").strip()
        link = (entry.findtext("link") or "").strip()
        pub_raw = entry.findtext("pubDate") or entry.findtext("published")
        published = None
        if pub_raw:
            try:
                published = parsedate_to_datetime(pub_raw)
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
        if not link or not published or not (start <= published <= end):
            continue
        items.append({
            "title": title, "url": link, "source": source,
            "published": published, "engagement": 0, "label": "",
            "summary": (entry.findtext("description") or "")[:280],
        })
    return items


def fetch_google(days: int) -> list[dict]:
    start, end = window(days)
    q = f"{AI_QUERY} after:{start.date()} before:{end.date()}"
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": q, "hl": "en-US", "gl": "US", "ceid": "US:en",
    })
    web = parse_rss(fetch_url(url), start, end, "google_news")
    q2 = f"{AI_QUERY} (site:x.com OR site:twitter.com) after:{start.date()} before:{end.date()}"
    url2 = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": q2, "hl": "en-US", "gl": "US", "ceid": "US:en",
    })
    tw = parse_rss(fetch_url(url2), start, end, "google_twitter")
    return web + tw


def fetch_hn(days: int) -> list[dict]:
    since = int(window(days)[0].timestamp())
    params = urllib.parse.urlencode({
        "query": HN_QUERY, "tags": "story",
        "numericFilters": f"created_at_i>{since}", "hitsPerPage": "100",
    })
    data = json.loads(fetch_url(f"https://hn.algolia.com/api/v1/search?{params}"))
    out = []
    for hit in data.get("hits", []):
        pts = int(hit.get("points") or 0)
        com = int(hit.get("num_comments") or 0)
        ts = hit.get("created_at_i")
        pub = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        out.append({
            "title": hit.get("title", "").strip(), "url": url, "source": "hacker_news",
            "published": pub, "engagement": pts + com * 2,
            "label": f"{pts} pts · {com} comments", "summary": "",
        })
    return out


def fetch_reddit(days: int) -> list[dict]:
    start, end = window(days)
    t = "day" if days <= 1 else "week" if days <= 7 else "month" if days <= 30 else "year"
    out = []
    for sub in REDDIT_SUBS:
        params = urllib.parse.urlencode({"t": t, "limit": "50"})
        url = f"https://www.reddit.com/r/{sub}/top.json?{params}"
        try:
            data = json.loads(fetch_url(url, {"User-Agent": UA}))
        except Exception:
            continue
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            pub = datetime.fromtimestamp(p.get("created_utc", 0), tz=timezone.utc)
            if not (start <= pub <= end):
                continue
            ups = int(p.get("ups") or 0)
            com = int(p.get("num_comments") or 0)
            link = p.get("url") or f"https://www.reddit.com{p.get('permalink', '')}"
            out.append({
                "title": p.get("title", "").strip(), "url": link, "source": "reddit",
                "published": pub, "engagement": ups + com * 2,
                "label": f"{ups} upvotes · {com} comments · r/{sub}",
                "summary": (p.get("selftext") or "")[:200],
            })
    return out


def merge(items: list[dict]) -> list[dict]:
    by_url: dict[str, dict] = {}
    tags: dict[str, set] = {}
    for it in items:
        key = it["url"].split("?")[0].rstrip("/").lower()
        tags.setdefault(key, set()).add(it["source"])
        if key not in by_url or it["engagement"] > by_url[key]["engagement"]:
            by_url[key] = {**it, "tags": tags[key]}
        else:
            by_url[key]["tags"] = tags[key]
    return list(by_url.values())


def score(it: dict, now: datetime, hits: int) -> float:
    import math
    w = {"hacker_news": 1.4, "reddit": 1.3, "google_twitter": 1.15, "google_news": 1.0}
    eng = math.log1p(it["engagement"]) * 12 * w.get(it["source"], 1.0) if it["engagement"] else 0
    rec = 0.5
    if it["published"]:
        age = max((now - it["published"]).total_seconds() / 3600, 0.5)
        rec = 1.0 + 2.5 * math.exp(-age / 48)
    viral = min(len(re.findall(
        r"\b(breaking|launch|released|open.?source|billion|GPT|Claude|Gemini|funding)\b",
        it["title"], re.I)) * 3, 12)
    return round(eng + rec * 5 + viral + max(hits - 1, 0) * 8, 2)


def run(days: int, top_n: int = 25) -> list[tuple[float, dict]]:
    start, end = window(days)
    raw: list[dict] = []
    for name, fn in [("Google", fetch_google), ("HN", fetch_hn), ("Reddit", fetch_reddit)]:
        try:
            batch = fn(days)
            print(f"  ✓ {name}: {len(batch)}", file=sys.stderr)
            raw.extend(batch)
        except Exception as e:
            print(f"  ✗ {name}: {e}", file=sys.stderr)
    merged = merge([i for i in raw if i.get("published") and start <= i["published"] <= end])
    now = datetime.now(timezone.utc)
    counts = {i["url"].split("?")[0].rstrip("/").lower(): len(i.get("tags", {i["source"]})) for i in merged}
    ranked = [(score(i, now, counts.get(i["url"].split("?")[0].rstrip("/").lower(), 1)), i) for i in merged]
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[:top_n]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", "-d", type=int, default=7)
    p.add_argument("--top", "-n", type=int, default=25)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    start, end = window(args.days)
    print(f"\nAI News Agent — strict window: last {args.days} day(s) ({start.date()} → {end.date()} UTC)\n", file=sys.stderr)
    ranked = run(args.days, args.top)
    if args.json:
        print(json.dumps([{
            "rank": i, "score": s, "title": it["title"], "url": it["url"],
            "sources": sorted(it.get("tags", {it["source"]})),
            "published": it["published"].isoformat() if it["published"] else None,
            "engagement_label": it.get("label", ""),
        } for i, (s, it) in enumerate(ranked, 1)], indent=2))
    else:
        for i, (s, it) in enumerate(ranked, 1):
            src = ", ".join(sorted(it.get("tags", {it["source"]})))
            when = it["published"].strftime("%Y-%m-%d") if it["published"] else "—"
            print(f"{i:2}. [{s:5.1f}] {it['title'][:75]}")
            print(f"    {it['url']}")
            if it.get("label"):
                print(f"    {it['label']}")
            print(f"    sources: {src} · {when}\n")


if __name__ == "__main__":
    main()
