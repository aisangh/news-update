"""HTML and plain-text report generators."""

import html
import json
import re
import textwrap
from datetime import datetime, timezone

from dateutil import parser as date_parser


def _esc(text: str) -> str:
    return html.escape(text or "")


def format_date_human(raw: str | None) -> str:
    """Format ISO date for human-readable display."""
    if not raw:
        return "Date unknown"
    try:
        dt = date_parser.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        return dt.strftime("%A, %B %d, %Y at %H:%M UTC")
    except (ValueError, TypeError):
        return raw


def _story_summary(story: dict) -> str:
    raw = (story.get("summary") or "").strip()
    if raw:
        clean = re.sub(r"<[^>]+>", "", html.unescape(raw))
        clean = re.sub(r"\s+", " ", clean).strip()
        if clean:
            return clean
    return "No summary available for this story."


def _first_published(story: dict) -> str | None:
    return story.get("first_published") or story.get("date")


def generate_html_report(
    stories: list[dict],
    *,
    days: int,
    total_scanned: int,
    sources_used: list[str],
    verified_count: int,
    output_path: str,
) -> None:
    now = datetime.now(timezone.utc)
    generated_at = now.strftime("%Y-%m-%d %H:%M UTC")
    n = len(stories)
    sources_str = ", ".join(sources_used) if sources_used else "RSS"

    cards_html = []
    for story in stories:
        rank = story.get("rank", 0)
        sc = story.get("source_count", 1)
        social = story.get("social_fallback")
        is_reddit = social == "reddit"
        verified = sc >= 3 and not is_reddit

        badges = []
        if verified:
            badges.append('<span class="badge verified">✅ Verified</span>')
        if is_reddit:
            badges.append('<span class="badge trending">📱 Reddit</span>')

        badge_html = " ".join(badges)
        source_chips = "".join(
            f'<span class="chip">{_esc(s)}</span>' for s in (story.get("sources") or [])
        )
        first_pub = _first_published(story)
        first_pub_display = _esc(format_date_human(first_pub))
        summary_text = _esc(_story_summary(story))
        hook = _esc(story.get("hook") or "")
        caption = _esc(story.get("caption") or "")
        hashtags = _esc(story.get("hashtags") or "")
        title = _esc(story.get("title") or "")
        url = _esc(story.get("url") or "#")

        data_attrs = (
            f'data-sources="{sc}" data-reddit="{"1" if is_reddit else "0"}" '
            f'data-date="{_esc(first_pub or "")}" data-rank="{rank}"'
        )

        cards_html.append(
            f"""
    <article class="story-card" {data_attrs}>
      <div class="card-header">
        <span class="rank-badge">#{rank}</span>
        <span class="source-badge">{sc} source{"s" if sc != 1 else ""}</span>
        {badge_html}
      </div>
      <h2><a href="{url}" target="_blank" rel="noopener">{title}</a></h2>
      <div class="chips">{source_chips}</div>
      <div class="story-meta">
        <p class="meta-row"><span class="meta-label">First published</span> {first_pub_display}</p>
        <div class="summary-block">
          <span class="meta-label">Summary</span>
          <p class="summary">{summary_text}</p>
        </div>
        <p class="meta-row link-row"><span class="meta-label">Article</span> <a href="{url}" target="_blank" rel="noopener">{url}</a></p>
      </div>
      <div class="reel-box">
        <h3>Reel Content</h3>
        <div class="copy-block">
          <label>Hook</label>
          <p class="copy-text hook-text">{hook}</p>
          <button type="button" class="copy-btn" data-copy="hook">📋 Copy</button>
        </div>
        <div class="copy-block">
          <label>Caption</label>
          <p class="copy-text caption-text">{caption}</p>
          <button type="button" class="copy-btn" data-copy="caption">📋 Copy</button>
        </div>
        <div class="copy-block">
          <label>Hashtags</label>
          <p class="copy-text hashtags-text">{hashtags}</p>
          <button type="button" class="copy-btn" data-copy="hashtags">📋 Copy</button>
        </div>
        <button type="button" class="copy-all-btn">Copy All</button>
        <textarea class="all-content" hidden>{hook}

{caption}

{hashtags}</textarea>
      </div>
    </article>"""
        )

    cards_joined = "\n".join(cards_html)

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI News Reel Report — {generated_at}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: system-ui, -apple-system, sans-serif;
      background: #0f0f0f;
      color: #e5e5e5;
      line-height: 1.6;
      padding: 1rem;
      max-width: 720px;
      margin: 0 auto;
    }}
    header {{
      text-align: center;
      padding: 2rem 0 1.5rem;
      border-bottom: 1px solid #333;
      margin-bottom: 1.5rem;
    }}
    h1 {{
      font-size: 1.75rem;
      background: linear-gradient(90deg, #7c3aed, #06b6d4);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }}
    .subtitle {{ color: #a3a3a3; font-size: 0.95rem; margin-top: 0.5rem; }}
    .stats-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      justify-content: center;
      margin-top: 1.25rem;
      font-size: 0.85rem;
    }}
    .stat {{
      background: #1a1a2e;
      padding: 0.5rem 1rem;
      border-radius: 8px;
      border: 1px solid #333;
    }}
    .stat strong {{ color: #06b6d4; }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-bottom: 1.5rem;
      align-items: center;
    }}
    .toolbar button, .toolbar select {{
      background: #1a1a2e;
      color: #e5e5e5;
      border: 1px solid #444;
      padding: 0.4rem 0.75rem;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.85rem;
    }}
    .toolbar button.active {{
      border-color: #7c3aed;
      background: #2d1f4e;
      color: #c4b5fd;
    }}
    .story-card {{
      background: #1a1a2e;
      border-radius: 12px;
      padding: 1.25rem;
      margin-bottom: 1.25rem;
      border: 1px solid #2a2a3e;
    }}
    .story-card.hidden {{ display: none; }}
    .card-header {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      align-items: center;
      margin-bottom: 0.75rem;
    }}
    .rank-badge {{
      background: linear-gradient(135deg, #7c3aed, #06b6d4);
      color: #fff;
      font-weight: 700;
      padding: 0.2rem 0.6rem;
      border-radius: 6px;
      font-size: 0.9rem;
    }}
    .source-badge {{
      background: #0f0f0f;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-size: 0.8rem;
      color: #06b6d4;
    }}
    .badge {{
      font-size: 0.75rem;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
    }}
    .badge.verified {{ background: #14532d; color: #86efac; }}
    .badge.trending {{ background: #7c2d12; color: #fdba74; }}
    .story-card h2 {{
      font-size: 1.15rem;
      margin-bottom: 0.75rem;
    }}
    .story-card h2 a {{ color: #e5e5e5; text-decoration: none; }}
    .story-card h2 a:hover {{ color: #06b6d4; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.75rem; }}
    .chip {{
      background: #0f0f0f;
      font-size: 0.7rem;
      padding: 0.15rem 0.45rem;
      border-radius: 999px;
      color: #a78bfa;
    }}
    .story-meta {{
      background: #0f0f0f;
      border-radius: 8px;
      padding: 1rem;
      margin-bottom: 1rem;
      border: 1px solid #2a2a3e;
    }}
    .meta-label {{
      display: block;
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #06b6d4;
      margin-bottom: 0.35rem;
      font-weight: 600;
    }}
    .meta-row {{
      font-size: 0.9rem;
      color: #d4d4d4;
      margin-bottom: 0.85rem;
    }}
    .meta-row .meta-label {{
      display: inline;
      margin-right: 0.35rem;
    }}
    .summary-block {{ margin-bottom: 0.85rem; }}
    .summary {{
      color: #e5e5e5;
      font-size: 0.95rem;
      line-height: 1.65;
      margin: 0;
    }}
    .link-row a {{
      color: #a78bfa;
      word-break: break-all;
      font-size: 0.85rem;
    }}
    .reel-box {{
      background: #0f0f0f;
      border-radius: 8px;
      padding: 1rem;
      margin-top: 1rem;
      border-left: 3px solid #7c3aed;
    }}
    .reel-box h3 {{
      font-size: 0.85rem;
      color: #06b6d4;
      margin-bottom: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .copy-block {{
      margin-bottom: 1rem;
      position: relative;
    }}
    .copy-block label {{
      font-size: 0.75rem;
      color: #7c3aed;
      display: block;
      margin-bottom: 0.25rem;
    }}
    .hook-text {{ color: #fbbf24; font-weight: 600; }}
    .copy-text {{ white-space: pre-wrap; font-size: 0.9rem; padding-right: 4rem; }}
    .copy-btn, .copy-all-btn {{
      background: #1a1a2e;
      border: 1px solid #7c3aed;
      color: #c4b5fd;
      padding: 0.25rem 0.5rem;
      border-radius: 4px;
      font-size: 0.75rem;
      cursor: pointer;
      margin-top: 0.25rem;
    }}
    .copy-btn {{ position: absolute; top: 0; right: 0; }}
    .copy-all-btn {{
      width: 100%;
      padding: 0.5rem;
      margin-top: 0.5rem;
      font-size: 0.85rem;
    }}
    footer {{
      text-align: center;
      padding: 2rem 0;
      color: #666;
      font-size: 0.85rem;
      border-top: 1px solid #333;
      margin-top: 2rem;
    }}
    footer a {{ color: #06b6d4; }}
  </style>
</head>
<body>
  <header>
    <h1>🤖 AI News Reel Report</h1>
    <p class="subtitle">Top {n} viral AI stories • Last {days} days • Generated {generated_at}</p>
    <div class="stats-bar">
      <span class="stat"><strong>{total_scanned}</strong> stories scanned</span>
      <span class="stat"><strong>{len(sources_used)}</strong> sources used</span>
      <span class="stat"><strong>{verified_count}</strong> confirmed on 3+ sources</span>
    </div>
  </header>

  <div class="toolbar">
    <span>Filter:</span>
    <button type="button" class="filter-btn active" data-filter="all">All</button>
    <button type="button" class="filter-btn" data-filter="verified">3+ Sources</button>
    <button type="button" class="filter-btn" data-filter="reddit">Reddit</button>
    <span style="margin-left:0.5rem">Sort:</span>
    <select id="sort-select">
      <option value="coverage">By Coverage</option>
      <option value="date">By Date</option>
    </select>
  </div>

  <div id="stories-container">
{cards_joined}
  </div>

  <footer>
    <p>Generated by AI News Finder • Free &amp; Open Source</p>
    <p><a href="https://github.com/" target="_blank" rel="noopener">Project README</a></p>
  </footer>

  <script>
    const container = document.getElementById('stories-container');

    function copyText(text, btn) {{
      navigator.clipboard.writeText(text).then(() => {{
        const orig = btn.textContent;
        btn.textContent = '✅ Copied!';
        setTimeout(() => {{ btn.textContent = orig; }}, 1500);
      }});
    }}

    document.querySelectorAll('.copy-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const block = btn.closest('.copy-block');
        const text = block.querySelector('.copy-text').textContent;
        copyText(text, btn);
      }});
    }});

    document.querySelectorAll('.copy-all-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const card = btn.closest('.story-card');
        const ta = card.querySelector('.all-content');
        copyText(ta.value, btn);
      }});
    }});

    let currentFilter = 'all';
    document.querySelectorAll('.filter-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        applyFilterSort();
      }});
    }});

    document.getElementById('sort-select').addEventListener('change', applyFilterSort);

    function applyFilterSort() {{
      const cards = Array.from(container.querySelectorAll('.story-card'));
      const sortBy = document.getElementById('sort-select').value;

      cards.forEach(card => {{
        const sc = parseInt(card.dataset.sources, 10);
        const isReddit = card.dataset.reddit === '1';
        let show = true;
        if (currentFilter === 'verified') show = sc >= 3 && !isReddit;
        if (currentFilter === 'reddit') show = isReddit;
        card.classList.toggle('hidden', !show);
      }});

      const visible = cards.filter(c => !c.classList.contains('hidden'));
      visible.sort((a, b) => {{
        if (sortBy === 'coverage') {{
          return parseInt(b.dataset.sources, 10) - parseInt(a.dataset.sources, 10);
        }}
        return (b.dataset.date || '').localeCompare(a.dataset.date || '');
      }});
      visible.forEach(c => container.appendChild(c));
    }}
  </script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)


def generate_text_report(
    stories: list[dict],
    *,
    days: int,
    total_scanned: int,
    sources_used: list[str],
    verified_count: int,
    output_path: str,
) -> None:
    """Write a beautifully formatted plain-text report for easy reading."""
    now = datetime.now(timezone.utc)
    generated_at = now.strftime("%Y-%m-%d %H:%M UTC")
    generated_date = now.strftime("%A, %B %d, %Y")
    
    lines = [
        "",
        "╔═══════════════════════════════════════════════════════════════════════╗",
        "║                    🤖 AI NEWS REEL REPORT 🤖                         ║",
        "╚═══════════════════════════════════════════════════════════════════════╝",
        "",
        f"📅 Generated: {generated_date}",
        f"🕐 Time: {generated_at}",
        f"📊 Period: Last {days} day(s)",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "📈 SUMMARY",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"  📡 Stories scanned:        {total_scanned}",
        f"  📰 Top stories selected:   {len(stories)}",
        f"  ✅ Verified (3+ sources):  {verified_count}",
        f"  🔗 Sources used:           {len(sources_used)}",
        "",
        "Sources: " + (", ".join(sources_used) if sources_used else "RSS feeds only"),
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📌 TOP {len(stories)} AI STORIES",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for i, story in enumerate(stories, 1):
        rank = story.get("rank", i)
        sc = story.get("source_count", 1)
        title = story.get("title") or ""
        sources = story.get("sources") or []
        url = story.get("url") or ""
        first_pub = format_date_human(_first_published(story))
        summary = _story_summary(story)
        hook = story.get("hook") or ""
        
        # Determine verification badge
        social = story.get("social_fallback")
        is_reddit = social == "reddit"
        verified = sc >= 3 and not is_reddit
        badge = "✅ VERIFIED" if verified else ("📱 REDDIT" if is_reddit else "")
        
        lines.extend([
            f"┌─ #{rank} {badge}".ljust(73, "─") + "┐",
            f"│",
            f"│  📰 {title}",
            f"│",
            f"│  📊 Coverage: {sc} source{'s' if sc != 1 else ''} → {', '.join(sources[:3])}{'...' if len(sources) > 3 else ''}",
            f"│  📅 First published: {first_pub}",
            f"│",
            f"│  📝 Summary:",
        ])
        
        # Word wrap summary to 65 chars for mobile readability
        summary_lines = textwrap.fill(summary, width=65).split('\n')
        for line in summary_lines:
            lines.append(f"│     {line}")
        
        lines.extend([
            f"│",
            f"│  🔗 Read more: {url[:50]}{'...' if len(url) > 50 else ''}",
        ])
        
        if hook:
            lines.append(f"│")
            lines.append(f"│  💡 Reel Hook:")
            hook_lines = textwrap.fill(hook, width=65).split('\n')
            for line in hook_lines:
                lines.append(f"│     {line}")
        
        lines.extend([
            f"│",
            f"└" + "─" * 71 + "┘",
            "",
        ])

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "✨ Report generated by AI News Finder",
        "🌐 https://github.com/aisangh/news-update",
        "",
        "💡 Tip: Open in a monospace font (Courier, Monaco, etc) for best display",
        "",
    ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def export_json(stories: list[dict], path: str, *, days: int) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "stories": [
            {
                **s,
                "first_published": _first_published(s),
                "first_published_display": format_date_human(_first_published(s)),
            }
            for s in stories
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
