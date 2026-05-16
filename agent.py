from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from config import TOP_N, window
from models import NewsItem
from scorer import merge_duplicates, score_item
from sources import (
    fetch_google_news,
    fetch_hacker_news,
    fetch_reddit,
    fetch_twitter,
)

console = Console()


def _fetch_all(days: int) -> list[NewsItem]:
    tasks = {
        "Google News": lambda: fetch_google_news(days),
        "Hacker News": lambda: fetch_hacker_news(days),
        "Reddit": lambda: fetch_reddit(days),
        "Twitter/X": lambda: fetch_twitter(days),
    }
    collected: list[NewsItem] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                batch = future.result()
                console.print(f"  [green]✓[/green] {name}: {len(batch)} items")
                collected.extend(batch)
            except Exception as exc:
                console.print(f"  [red]✗[/red] {name}: {exc}")
    return collected


def _strict_filter(items: list[NewsItem], days: int) -> list[NewsItem]:
    start, end = window(days)
    kept: list[NewsItem] = []
    for item in items:
        if item.published is None:
            continue
        pub = item.published
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        if start <= pub <= end:
            kept.append(item)
    return kept


def run_agent(days: int, top_n: int | None = None) -> list[tuple[float, NewsItem]]:
    top_n = top_n or TOP_N
    start, end = window(days)

    console.print("\n[bold cyan]AI News Virality Agent[/bold cyan]")
    console.print(
        f"Strict window: last [bold]{days}[/bold] day(s) "
        f"({start.date()} → {end.date()} UTC)\n"
    )
    console.print("[dim]Fetching sources…[/dim]")

    raw = _fetch_all(days)
    merged = merge_duplicates(_strict_filter(raw, days))

    now = datetime.now(timezone.utc)
    source_counts: dict[str, int] = {}
    for item in merged:
        source_counts[item.virality_key()] = len(item.tags) or 1

    ranked: list[tuple[float, NewsItem]] = []
    for item in merged:
        hits = source_counts.get(item.virality_key(), 1)
        s = score_item(item, now, hits)
        ranked.append((s, item))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[:top_n]


def print_report(ranked: list[tuple[float, NewsItem]], days: int) -> None:
    table = Table(
        title=f"Top AI News (last {days} days) — ranked by virality",
        show_lines=True,
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Score", justify="right", style="bold magenta")
    table.add_column("Title", max_width=52)
    table.add_column("Engagement", max_width=22)
    table.add_column("Sources", max_width=14)
    table.add_column("When", max_width=10)

    for i, (score, item) in enumerate(ranked, 1):
        when = item.published.strftime("%Y-%m-%d") if item.published else "—"
        sources = ", ".join(item.tags) if item.tags else item.source
        table.add_row(
            str(i),
            f"{score:.1f}",
            item.title[:80],
            item.engagement_label or "—",
            sources[:14],
            when,
        )

    console.print()
    console.print(table)
    console.print("\n[bold]Details[/bold]\n")
    for i, (score, item) in enumerate(ranked, 1):
        console.print(f"[bold]{i}. [{score:.1f}] {item.title}[/bold]")
        console.print(f"   {item.url}")
        if item.engagement_label:
            console.print(f"   [dim]{item.engagement_label}[/dim]")
        if item.summary:
            console.print(f"   [dim]{item.summary[:200]}[/dim]")
        console.print()
