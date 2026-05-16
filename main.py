#!/usr/bin/env python3
"""AI news virality agent — scan web, rank by viral signal, strict date window."""

import argparse
import json
import sys
from datetime import datetime, timezone

from agent import print_report, run_agent
from models import NewsItem


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan AI news from Google, Twitter, Reddit, HN; rank by virality.",
    )
    parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=7,
        help="Strict search window: last N days only (default: 7)",
    )
    parser.add_argument(
        "--top",
        "-n",
        type=int,
        default=None,
        help="Number of top stories to return",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of formatted report",
    )
    args = parser.parse_args()

    if args.days < 1:
        print("Error: --days must be at least 1", file=sys.stderr)
        return 1

    ranked = run_agent(args.days, top_n=args.top)

    if args.json:
        payload = [
            {
                "rank": i,
                "virality_score": score,
                "title": item.title,
                "url": item.url,
                "sources": item.tags or [item.source],
                "published": item.published.isoformat() if item.published else None,
                "engagement": item.engagement,
                "engagement_label": item.engagement_label,
                "summary": item.summary,
            }
            for i, (score, item) in enumerate(ranked, 1)
        ]
        print(json.dumps(payload, indent=2))
    else:
        print_report(ranked, args.days)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
