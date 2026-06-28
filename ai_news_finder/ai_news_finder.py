#!/usr/bin/env python3
"""AI News Finder — curate top 10 viral AI stories for Instagram Reels."""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from collectors import collect_reddit, collect_rss
from collectors.rss import enrich_story_summaries
from discord_notifier import send_error_notification, send_report_file
from generators import generate_html_report, generate_reel_content, generate_text_report
from generators.report import export_json
from hf_ranker import should_use_hf_ranker
from llm_summary import should_use_summary_model, summary_model_name
from processors import filter_ai_stories, group_stories, select_top_stories

_pkg_dir = Path(__file__).resolve().parent
if (_pkg_dir / ".env").is_file():
    load_dotenv(_pkg_dir / ".env")

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger(__name__)


def _pad(msg: str, width: int = 36) -> str:
    return msg.ljust(width)


def _stage(msg: str, detail: str = "") -> None:
    line = _pad(msg)
    print(f"{line} {detail}" if detail else line)


def _preview_titles(stories: list[dict], limit: int = 3) -> str:
    titles = [str(s.get("title") or "").strip() for s in stories[:limit] if s.get("title")]
    if not titles:
        return ""
    return " | ".join(titles)


def _running_in_kaggle() -> bool:
    return bool(
        os.getenv("KAGGLE_KERNEL_RUN_TYPE")
        or os.getenv("KAGGLE_URL_BASE")
        or Path("/kaggle/working").exists()
    )


def _default_reports_dir() -> Path:
    custom_dir = os.getenv("AI_NEWS_REPORTS_DIR")
    if custom_dir:
        return Path(custom_dir).expanduser()
    if _running_in_kaggle():
        return Path("/kaggle/working/reports")
    return _pkg_dir.parent / "reports"


def _should_enrich_stories() -> bool:
    if os.getenv("AI_NEWS_ENRICH_STORIES") == "1":
        return True
    if os.getenv("AI_NEWS_ENRICH_STORIES") == "0":
        return False
    return True


def _enrichment_limit(default: int) -> int:
    raw = os.getenv("AI_NEWS_ENRICH_TOP_K")
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return default


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Curate top 10 viral AI news stories for Instagram Reels.",
    )
    parser.add_argument(
        "--days",
        type=int,
        required=True,
        help="How many past days of news to scan",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of top stories to select (default: 10)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom HTML output filename (default: report_YYYY-MM-DD.html)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="export_json",
        help="Also export a JSON file alongside the HTML",
    )
    parser.add_argument(
        "--reports-dir",
        type=str,
        default=None,
        help=(
            "Directory for generated reports. Defaults to AI_NEWS_REPORTS_DIR, "
            "then /kaggle/working/reports on Kaggle, otherwise ./reports"
        ),
    )
    args = parser.parse_args()

    if args.days < 1:
        print("Error: --days must be at least 1", file=sys.stderr)
        send_error_notification(
            title="❌ AI News Finder Configuration Error",
            message="Invalid --days parameter provided.",
            error_details="--days must be at least 1",
        )
        return 1

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    reports_dir = Path(args.reports_dir).expanduser() if args.reports_dir else _default_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Reports directory: {reports_dir}")

    output_file = args.output or f"report_{today}.html"
    output_path = Path(output_file)
    if not output_path.is_absolute():
        output_path = reports_dir / output_path.name
    text_path = output_path.with_suffix(".txt")

    print("Running AI News Finder...")

    active_models: list[str] = []
    if should_use_hf_ranker():
        active_models.append("hf")
    if should_use_summary_model():
        active_models.append("qwen")
    if active_models:
        print(f"🧠 Models active: {', '.join(active_models)}")

    rss_stories = collect_rss(cutoff)
    rss_ai = filter_ai_stories(rss_stories)

    all_raw = rss_ai
    if not all_raw:
        print(
            "\nNo stories collected from any source. Check your network connection "
            "and try again.",
            file=sys.stderr,
        )
        send_error_notification(
            title="❌ AI News Finder Collection Failed",
            message="No stories were collected from any source.",
            error_details="Check your network connection and try again. Verify RSS feeds are accessible.",
        )
        return 1

    total_scanned = len(all_raw)

    groups = group_stories(all_raw)

    primary_pool = [g for g in groups if g.get("source_count", 0) >= 3]

    reddit_stories: list[dict] = []
    if len(primary_pool) < 10:
        reddit_raw = collect_reddit()
        reddit_stories = filter_ai_stories(reddit_raw) if reddit_raw else []
        if not reddit_stories and reddit_raw:
            reddit_stories = reddit_raw

    selected, _stats = select_top_stories(groups, reddit_stories, limit=args.limit)
    print(f"📊 Final selection: {len(selected)} stories")

    if not selected:
        print("\nNo AI stories matched your criteria. Try increasing --days.", file=sys.stderr)
        send_error_notification(
            title="❌ AI News Finder Selection Failed",
            message="No AI stories matched the selection criteria.",
            error_details=f"Scanned {len(groups)} story groups but none matched filters. Try increasing --days.",
        )
        return 1

    if _should_enrich_stories():
        enrich_limit = min(len(selected), _enrichment_limit(len(selected)))
        if enrich_limit > 0:
            print(f"🧠 Enriching {enrich_limit} stories...")

            def _enrich_progress(idx: int, total: int, story: dict, status: str) -> None:
                title = str(story.get("title") or "").strip()
                print(f"    [{idx}/{total}] {status} {title}")

            enrich_story_summaries(selected[:enrich_limit], progress=_enrich_progress)
        else:
            print("🧠 Enrichment skipped.")
    else:
        print("🧠 Enrichment skipped.")

    for story in selected:
        generate_reel_content(story)
    print("✍️ Generated captions.")

    # Sources used
    sources_used: list[str] = []
    seen_src: set[str] = set()
    for story in selected:
        for s in story.get("sources") or []:
            if s and s not in seen_src:
                seen_src.add(s)
                sources_used.append(s)

    verified_count = sum(
        1 for s in selected
        if s.get("source_count", 0) >= 3 and not s.get("social_fallback")
    )

    report_kwargs = dict(
        days=args.days,
        total_scanned=total_scanned,
        sources_used=sources_used,
        verified_count=verified_count,
    )
    generate_html_report(selected, output_path=str(output_path), **report_kwargs)
    generate_text_report(selected, output_path=str(text_path), **report_kwargs)
    print("🧾 Reports rendered.")

    if args.export_json:
        json_path = output_path.with_suffix(".json")
        export_json(selected, str(json_path), days=args.days)
        print(f"📄 JSON saved: {json_path.name}")

    # Send the HTML report file to Discord
    if output_path.exists():
        send_report_file(
            str(output_path.resolve()),
            f"📱 Interactive Report - {today}\n{len(selected)} top AI stories • {len(sources_used)} sources • Click to expand details"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
