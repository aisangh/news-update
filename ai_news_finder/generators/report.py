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

        badges_html = ""
        if verified:
            badges_html += '<span class="badge verified">✅ Verified</span>'
        if is_reddit:
            badges_html += '<span class="badge trending">📱 Reddit</span>'

        source_chips = "".join(
            f'<span class="chip">{_esc(s)}</span>' for s in (story.get("sources") or [])[:5]
        )
        first_pub = _first_published(story)
        first_pub_display = _esc(format_date_human(first_pub))
        summary_text = _esc(_story_summary(story))
        hook = _esc(story.get("hook") or "")
        title = _esc(story.get("title") or "")
        url = _esc(story.get("url") or "#")
        sources = story.get("sources") or []

        cards_html.append(
            f"""
    <div class="story-card">
      <div class="story-header">
        <div class="rank-badge">#{rank}</div>
        <div class="story-title-section">
          <div class="story-meta-row">
            <span class="badge sources">{sc} source{'s' if sc != 1 else ''}</span>
            {badges_html}
          </div>
          <h2><a href="{url}" target="_blank" rel="noopener">{title}</a></h2>
        </div>
      </div>
      
      <div class="summary">{summary_text}</div>
      
      {f'<div class="hook">💡 {hook}</div>' if hook else ''}
      
      <button class="collapsible-toggle">
        ℹ️ More Details <span class="toggle-icon">▼</span>
      </button>
      
      <div class="metadata">
        <div class="metadata-item">
          <span class="metadata-label">📅 Published</span>
          <span class="metadata-value">{first_pub_display}</span>
        </div>
        
        <div class="metadata-item">
          <span class="metadata-label">📡 Sources ({len(sources)})</span>
          <div class="chips">
            {''.join(f'<span class="chip">{_esc(s)}</span>' for s in sources)}
          </div>
        </div>
        
        <div class="metadata-item">
          <span class="metadata-label">🔗 Read Article</span>
          <span class="metadata-value" style="word-break: break-all;">{url}</span>
        </div>
      </div>
    </div>"""
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
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
      background: #0a0e27;
      color: #e5e5e5;
      line-height: 1.6;
      padding: 0;
      margin: 0;
    }}
    
    header {{
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      padding: 2rem 1rem 1.5rem;
      text-align: center;
      position: sticky;
      top: 0;
      z-index: 100;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }}
    
    h1 {{
      font-size: 2rem;
      color: white;
      margin-bottom: 0.5rem;
      font-weight: 700;
    }}
    
    .subtitle {{
      color: rgba(255,255,255,0.9);
      font-size: 0.95rem;
      margin-bottom: 1rem;
    }}
    
    .stats-bar {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
      margin-top: 1rem;
      font-size: 0.85rem;
    }}
    
    .stat {{
      background: rgba(255,255,255,0.1);
      padding: 0.75rem;
      border-radius: 8px;
      border: 1px solid rgba(255,255,255,0.2);
      color: white;
    }}
    
    .stat-value {{ 
      font-size: 1.5rem;
      font-weight: 700;
      display: block;
    }}
    
    .stat-label {{
      font-size: 0.75rem;
      opacity: 0.9;
      margin-top: 0.25rem;
    }}
    
    main {{
      max-width: 100%;
      padding: 0;
    }}
    
    .story-card {{
      background: #1a1f3a;
      margin: 0;
      padding: 1.25rem;
      border: none;
      border-bottom: 1px solid #2a2f4a;
      transition: all 0.3s ease;
    }}
    
    .story-card:active {{
      background: #252b40;
    }}
    
    .story-header {{
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      margin-bottom: 1rem;
    }}
    
    .rank-badge {{
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      font-weight: 700;
      padding: 0.5rem 0.75rem;
      border-radius: 6px;
      font-size: 1rem;
      flex-shrink: 0;
      min-width: 35px;
      text-align: center;
    }}
    
    .story-title-section {{
      flex: 1;
    }}
    
    .story-card h2 {{
      font-size: 1.1rem;
      line-height: 1.4;
      margin-bottom: 0.5rem;
      color: white;
    }}
    
    .story-card h2 a {{
      color: white;
      text-decoration: none;
    }}
    
    .story-card h2 a:active {{
      color: #667eea;
    }}
    
    .story-meta-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-bottom: 0.75rem;
      font-size: 0.8rem;
    }}
    
    .badge {{
      padding: 0.25rem 0.5rem;
      border-radius: 4px;
      font-size: 0.7rem;
      font-weight: 600;
    }}
    
    .badge.verified {{
      background: #10b981;
      color: white;
    }}
    
    .badge.trending {{
      background: #f59e0b;
      color: white;
    }}
    
    .badge.sources {{
      background: #3b82f6;
      color: white;
    }}
    
    .summary {{
      background: rgba(102, 126, 234, 0.1);
      padding: 1rem;
      border-radius: 8px;
      margin-bottom: 0.75rem;
      border-left: 3px solid #667eea;
      font-size: 0.95rem;
      line-height: 1.6;
      color: #e5e5e5;
    }}
    
    .hook {{
      background: rgba(245, 158, 11, 0.1);
      padding: 0.75rem;
      border-radius: 6px;
      margin-bottom: 0.75rem;
      border-left: 3px solid #f59e0b;
      font-weight: 600;
      font-size: 0.95rem;
      color: #fbbf24;
    }}
    
    .collapsible-toggle {{
      background: transparent;
      border: 1px solid #3b82f6;
      color: #60a5fa;
      padding: 0.5rem 0.75rem;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 600;
      width: 100%;
      text-align: left;
      transition: all 0.2s ease;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    
    .collapsible-toggle:active {{
      background: #1e3a8a;
      border-color: #60a5fa;
    }}
    
    .toggle-icon {{
      display: inline-block;
      transition: transform 0.2s ease;
    }}
    
    .collapsible-toggle.open .toggle-icon {{
      transform: rotate(180deg);
    }}
    
    .metadata {{
      max-height: 0;
      overflow: hidden;
      transition: max-height 0.3s ease;
      background: rgba(59, 130, 246, 0.05);
      border-radius: 6px;
    }}
    
    .metadata.open {{
      max-height: 500px;
      padding: 1rem;
      border: 1px solid #1e40af;
    }}
    
    .metadata-item {{
      margin-bottom: 0.75rem;
      font-size: 0.85rem;
    }}
    
    .metadata-label {{
      color: #60a5fa;
      font-weight: 600;
      margin-bottom: 0.2rem;
      display: block;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    
    .metadata-value {{
      color: #d4d4d8;
      word-break: break-word;
    }}
    
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      margin-top: 0.5rem;
    }}
    
    .chip {{
      background: #1e40af;
      color: #60a5fa;
      padding: 0.25rem 0.5rem;
      border-radius: 12px;
      font-size: 0.75rem;
    }}
    
    footer {{
      text-align: center;
      padding: 2rem 1rem;
      color: #666;
      font-size: 0.85rem;
      border-top: 1px solid #2a2f4a;
      margin-top: 2rem;
    }}
    
    footer a {{
      color: #667eea;
      text-decoration: none;
    }}
    
    /* Mobile optimizations */
    @media (max-width: 600px) {{
      h1 {{
        font-size: 1.5rem;
      }}
      
      .stats-bar {{
        grid-template-columns: 1fr 1fr;
      }}
      
      .story-card {{
        padding: 1rem;
      }}
      
      .story-card h2 {{
        font-size: 1rem;
      }}
      
      .summary {{
        font-size: 0.9rem;
        padding: 0.75rem;
      }}
    }}
    
    @media (max-width: 400px) {{
      header {{
        padding: 1.5rem 0.75rem 1rem;
      }}
      
      h1 {{
        font-size: 1.3rem;
      }}
      
      .subtitle {{
        font-size: 0.85rem;
      }}
      
      .stat-value {{
        font-size: 1.25rem;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>🤖 AI News Report</h1>
    <p class="subtitle">Top {n} viral AI stories • {days} day{'s' if days != 1 else ''} • {generated_at}</p>
    <div class="stats-bar">
      <div class="stat">
        <span class="stat-value">{total_scanned}</span>
        <span class="stat-label">📡 Scanned</span>
      </div>
      <div class="stat">
        <span class="stat-value">{verified_count}</span>
        <span class="stat-label">✅ Verified</span>
      </div>
    </div>
  </header>

  <main id="stories-container">
{cards_joined}
  </main>

  <footer>
    <p>✨ Generated by AI News Finder • Free & Open Source</p>
    <p><a href="https://github.com/aisangh/news-update" target="_blank" rel="noopener">📖 View on GitHub</a></p>
  </footer>

  <script>
    // Toggle metadata sections
    document.querySelectorAll('.collapsible-toggle').forEach(toggle => {{
      toggle.addEventListener('click', function() {{
        const metadata = this.nextElementSibling;
        this.classList.toggle('open');
        metadata.classList.toggle('open');
      }});
    }});
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
