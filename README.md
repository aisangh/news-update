# AI News Virality Agent (free, no API keys)

Finds **real AI news articles** trending across the web — with **resolved publisher URLs**, not Google redirect links.

## Quick start

```bash
./run.sh 7
```

## Free sources used

| Source | What it does | Cost |
|--------|----------------|------|
| **Google News RSS** | Headlines + viral + X/Twitter + YouTube search | Free |
| **Publisher RSS** | TechCrunch, Verge, Ars, Wired, MIT TR, VentureBeat, 404 Media, BBC Tech | Free |
| **GDELT** | Global news index — confirms stories appear in world press | Free |
| **Reddit JSON** | Article links shared on tech/AI subreddits | Free |
| **Hacker News Algolia** | Stories linking to news sites | Free |
| **URL resolver** | Follows redirects so Google links → real Forbes/NYT/etc. URLs | Free |

No OpenAI, no paid NewsAPI, no Twitter API required.

## Ranking (two rounds, target **15** by default)

**Round 1 — news agencies:** only stories with **2+ distinct news sites**. Rank by outlet count → tier‑1 outlets → Twitter → YouTube → score.

**Round 2 — fill to N (default 15):** if round 1 yields **fewer than N** picks, add more stories that still have **at least 1 real news article**, not already chosen. Rank by **X/Twitter mentions first**, then YouTube → outlet count → tier‑1 → GDELT → score. Items with any X pickup are listed before those with none.

Report lines are tagged **`[R1·news]`** or **`[R2·X-fill]`**.

## Output includes

- **Real article URL** (resolved from Google when needed)
- **Publisher name** (forbes.com, nytimes.com, …)
- **Verification** — multiple outlets, Twitter + article, or GDELT
- **Trending platforms** — where the story is buzzing
- **More coverage** — other outlets writing the same story
- **Reel hooks** — angles for short-form content

## Flags

```bash
node agent.mjs --days 7
node agent.mjs --days 2 --json
node agent.mjs --days 7 --top 15     # default is 15
node agent.mjs --days 7 --no-save     # skip writing reports/latest-7days.txt
```

## Optional

Copy `.env.example` → `.env` and set `X_BEARER_TOKEN` only if you use the **Python** path with direct Twitter API (Node agent does not need it).
