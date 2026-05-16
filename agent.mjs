#!/usr/bin/env node
/**
 * AI News Agent v3.1 — real article URLs, free multi-source verification
 * Usage: node agent.mjs --days 7
 */

import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { fetchGdelt } from "./lib/gdelt.mjs";
import { OUTLET_RSS } from "./lib/outlet-rss.mjs";
import { resolveBatch } from "./lib/resolve-url.mjs";

const __dir = dirname(fileURLToPath(import.meta.url));

const AI_MUST =
  /\b(ai\b|artificial intelligence|chatgpt|gpt-?4|gpt-?5|openai|claude|gemini|anthropic|copilot|sora|robot|humanoid|deepfake|generative|nvidia|machine learning|agi)\b/i;

const AI_QUERY =
  '(AI OR ChatGPT OR OpenAI OR Claude OR Gemini OR Anthropic OR Sora OR ' +
  '"artificial intelligence" OR robot OR humanoid OR deepfake)';

const GOOGLE_VIRAL_QUERY =
  '(AI OR ChatGPT OR OpenAI OR Claude OR Gemini OR Sora OR robot) ' +
  '(viral OR trending OR "goes viral" OR shocking OR banned OR lawsuit)';

const UA = "ai-news-agent/3.1";

const NON_ARTICLE =
  /^(https?:\/\/)?(www\.)?(reddit\.com\/(gallery|r\/|comments)|i\.redd\.it|v\.redd\.it|imgur\.|news\.ycombinator\.com\/item|medium\.com\/@|unix\.foo|\.github\.io|jpain\.io)/i;

const NEWS_PUBLISHER =
  /(nytimes|washingtonpost|wsj\.com|bbc\.|bbc\.co|cnn\.com|reuters\.com|bloomberg|forbes\.com|theverge|wired\.com|theguardian|techcrunch|businessinsider|arstechnica|fastcompany|tomshardware|404media|theatlantic|independent\.co|apnews\.com|npr\.org|axios|politico|ft\.com|economist|yahoo\.com\/news|nbcnews|fortune\.com|cnbc\.com|gizmodo|venturebeat|technologyreview|semianalysis|openai\.com|anthropic\.com|deepmind\.google)/i;

const TIER1 = /(nytimes|wsj\.com|reuters|bloomberg|bbc\.|washingtonpost|theguardian|apnews|ft\.com|economist)/i;

const REEL_HOOKS = [
  { re: /\b(robot|humanoid|figure\s*0|tesla\s*bot)\b/i, tag: "🤖 Visual hook" },
  { re: /\b(sora|video|deepfake|animation)\b/i, tag: "🎬 Reel-ready" },
  { re: /\b(banned|fired|lawsuit|sued|shutdown|scandal|leak|hack)\b/i, tag: "😱 Controversy" },
  { re: /\b(billion|million|funding|settlement)\b/i, tag: "💰 Money angle" },
  { re: /\b(jobs?|replace|layoff|unemployment)\b/i, tag: "⚠️ Jobs fear" },
  { re: /\b(viral|trending|shocking|insane)\b/i, tag: "🔥 Trending" },
  { re: /\b(musk|altman|zuckerberg|bezos|pichai)\b/i, tag: "👤 Big name" },
];

function window(days) {
  const end = new Date();
  const start = new Date(end.getTime() - days * 86400000);
  return { start, end };
}

function isAi(text) {
  return AI_MUST.test(text || "");
}

function cleanTitle(title) {
  return (title || "")
    .replace(/\s*[-–|]\s*[^-|]{2,40}$/i, "")
    .trim();
}

function normalizeStoryKey(title) {
  return cleanTitle(title)
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\b(the|a|an|to|of|in|on|for|and|or|is|are|was|were|after|says|said)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .filter((w) => w.length > 3)
    .slice(0, 8)
    .join(" ");
}

function getDomain(url) {
  try {
    const h = new URL(url).hostname.replace(/^www\./, "");
    if (h.includes("news.google.com")) return "Google News";
    if (h.includes("x.com") || h.includes("twitter.com")) return "Twitter/X";
    return h;
  } catch {
    return "";
  }
}

/** Distinct real news site hostnames (not Google redirect, not social). */
function distinctNewsDomains(sortedArticles) {
  const set = new Set();
  for (const a of sortedArticles) {
    const u = a.resolved || a.url;
    if (!u || /twitter\.com|x\.com|youtube\.com|youtu\.be/i.test(u)) continue;
    let host;
    try {
      host = new URL(u).hostname.replace(/^www\./, "");
    } catch {
      continue;
    }
    if (!host || host.includes("google") || host === "reddit.com") continue;
    if (!isNewsArticle(u)) continue;
    set.add(host);
  }
  return set;
}

function isNewsArticle(url) {
  if (!url || NON_ARTICLE.test(url)) return false;
  if (/news\.google\.com\/rss\/articles/.test(url)) return true;
  if (NEWS_PUBLISHER.test(url)) return true;
  try {
    const u = new URL(url);
    const path = u.pathname;
    if (/\.(php|html?|aspx)$/.test(path)) return true;
    if (/\/(news|article|story|politics|technology|business|world|sci-tech|tech)\//i.test(path)) return true;
    if (path.split("/").filter(Boolean).length >= 2 && !u.hostname.includes("reddit")) return true;
  } catch {
    return false;
  }
  return false;
}

function isMainstream(url) {
  return TIER1.test(url) || NEWS_PUBLISHER.test(url);
}

function reelHooks(title) {
  return [...new Set(REEL_HOOKS.filter((h) => h.re.test(title)).map((h) => h.tag))];
}

async function fetchJson(url, headers = {}) {
  const res = await fetch(url, { headers: { "User-Agent": UA, ...headers } });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function fetchText(url) {
  const res = await fetch(url, { headers: { "User-Agent": UA } });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.text();
}

function parseRssDate(raw) {
  if (!raw) return null;
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? null : d;
}

function parseRss(xml, start, end, platform) {
  const items = [];
  const reItem = /<item>([\s\S]*?)<\/item>/gi;
  let m;
  while ((m = reItem.exec(xml))) {
    const block = m[1];
    let title = (block.match(/<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/title>/i) || [])[1]
      ?.replace(/<[^>]+>/g, "")
      .trim();
    const link = (block.match(/<link>([^<]+)<\/link>/i) || [])[1]?.trim();
    const pubRaw =
      (block.match(/<pubDate>([^<]+)<\/pubDate>/i) || block.match(/<published>([^<]+)<\/published>/i) || [])[1];
    const published = parseRssDate(pubRaw);
    if (!title || !link || !published || published < start || published > end) continue;
    if (!isAi(title)) continue;

    const isTwitter = platform === "twitter" || /x\.com|twitter\.com/i.test(link);
    if (platform === "twitter" && !isTwitter && !isNewsArticle(link)) continue;
    if (platform === "news" && !isNewsArticle(link) && !/news\.google\.com/.test(link)) continue;
    if (platform === "outlet_rss" && !isNewsArticle(link)) continue;

    title = cleanTitle(title);
    items.push({
      title,
      url: link,
      platform,
      published,
      engagement: 0,
      domain: getDomain(link),
    });
  }
  return items;
}

async function fetchOutletRss(days) {
  const { start, end } = window(days);
  const all = [];
  await Promise.all(
    OUTLET_RSS.map(async ({ label, url }) => {
      try {
        const xml = await fetchText(url);
        const items = parseRss(xml, start, end, "outlet_rss");
        items.forEach((i) => {
          i.outlet = label;
        });
        all.push(...items);
      } catch {
        /* feed unavailable */
      }
    }),
  );
  return all;
}

async function fetchGoogle(days) {
  const { start, end } = window(days);
  const after = start.toISOString().slice(0, 10);
  const before = end.toISOString().slice(0, 10);
  const base = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q=";
  const queries = [
    { q: `${AI_QUERY} after:${after} before:${before}`, platform: "news" },
    { q: `${GOOGLE_VIRAL_QUERY} after:${after} before:${before}`, platform: "news" },
    {
      q: `${AI_QUERY} (site:x.com OR site:twitter.com) after:${after} before:${before}`,
      platform: "twitter",
    },
    {
      q: `${AI_QUERY} (site:youtube.com) after:${after} before:${before}`,
      platform: "youtube",
    },
  ];
  const batches = await Promise.all(
    queries.map(async ({ q, platform }) => {
      const xml = await fetchText(base + encodeURIComponent(q));
      return parseRss(xml, start, end, platform);
    }),
  );
  return batches.flat();
}

async function fetchHN(days) {
  const since = Math.floor(window(days).start.getTime() / 1000);
  const params = new URLSearchParams({
    query: "AI",
    tags: "story",
    numericFilters: `created_at_i>${since}`,
    hitsPerPage: "80",
  });
  const data = await fetchJson(`https://hn.algolia.com/api/v1/search?${params}`);
  return (data.hits || [])
    .map((hit) => {
      const title = cleanTitle(hit.title?.trim() || "");
      const url = hit.url || "";
      if (!isAi(title) || !isNewsArticle(url)) return null;
      return {
        title,
        url,
        platform: "hacker_news",
        published: hit.created_at_i ? new Date(hit.created_at_i * 1000) : null,
        engagement: (hit.points || 0) + (hit.num_comments || 0) * 2,
        domain: getDomain(url),
      };
    })
    .filter(Boolean);
}

async function fetchRedditArticles(days) {
  const { start, end } = window(days);
  const subs = ["technology", "artificial", "singularity", "OpenAI", "Futurology"];
  const t = days <= 1 ? "day" : days <= 7 ? "week" : "month";
  const all = [];
  await Promise.all(
    subs.map(async (sub) => {
      try {
        const data = await fetchJson(
          `https://www.reddit.com/r/${sub}/top.json?t=${t}&limit=40`,
          { "User-Agent": UA },
        );
        for (const child of data?.data?.children || []) {
          const p = child.data;
          if (p.is_self) continue;
          const title = cleanTitle(p.title?.trim() || "");
          const url = p.url || "";
          if (!isAi(title) || !isNewsArticle(url)) continue;
          const published = new Date((p.created_utc || 0) * 1000);
          if (published < start || published > end) continue;
          all.push({
            title,
            url,
            platform: "reddit",
            published,
            engagement: (p.ups || 0) + (p.num_comments || 0) * 2,
            domain: getDomain(url),
            label: `${p.ups} upvotes on r/${sub}`,
          });
        }
      } catch {
        /* skip */
      }
    }),
  );
  return all;
}

function titleWords(title) {
  return new Set(normalizeStoryKey(title).split(" ").filter((w) => w.length > 3));
}

function titleSimilarity(a, b) {
  const wa = titleWords(a);
  const wb = titleWords(b);
  if (!wa.size || !wb.size) return 0;
  let inter = 0;
  for (const w of wa) if (wb.has(w)) inter++;
  return inter / Math.max(wa.size, wb.size);
}

function keywordOverlap(a, b) {
  const wa = titleWords(a);
  const wb = titleWords(b);
  let n = 0;
  for (const w of wa) if (wb.has(w)) n++;
  return n;
}

const ENTITY_RE =
  /\b(openai|chatgpt|claude|gemini|anthropic|meta|google|microsoft|amazon|nvidia|musk|altman|zuckerberg|sora|robot|humanoid|southwest|princeton|figure|deepseek|codex)\b/gi;

function extractEntities(text) {
  return new Set((text.match(ENTITY_RE) || []).map((e) => e.toLowerCase()));
}

function entityOverlap(a, b) {
  const ea = extractEntities(a);
  const eb = extractEntities(b);
  let n = 0;
  for (const e of ea) if (eb.has(e)) n++;
  return n;
}

function clusterStories(items) {
  const twitterItems = items.filter(
    (i) => i.platform === "twitter" || /x\.com|twitter\.com/i.test(i.url),
  );
  const youtubeItems = items.filter((i) => i.platform === "youtube" || /youtube\.com|youtu\.be/i.test(i.url));
  const coreItems = items.filter(
    (i) =>
      i.platform !== "twitter" &&
      i.platform !== "youtube" &&
      !/x\.com|twitter\.com/i.test(i.url),
  );

  const clusters = [];

  for (const item of coreItems) {
    let best = null;
    let bestSim = 0.48;
    for (const c of clusters) {
      const sim = titleSimilarity(item.title, c.title);
      const ents = entityOverlap(item.title, c.title);
      const score = sim + ents * 0.12;
      if (score > bestSim) {
        bestSim = score;
        best = c;
      }
    }
    if (best) {
      best.items.push(item);
      if (item.engagement > best.maxEngagement) best.maxEngagement = item.engagement;
      if (item.published && (!best.published || item.published > best.published))
        best.published = item.published;
    } else {
      clusters.push({
        title: item.title,
        items: [item],
        published: item.published,
        maxEngagement: item.engagement || 0,
      });
    }
  }

  for (const social of [...twitterItems, ...youtubeItems]) {
    let best = null;
    let bestScore = 2;
    for (const c of clusters) {
      const kw = keywordOverlap(social.title, c.title);
      const ent = entityOverlap(social.title, c.title);
      const sim = titleSimilarity(social.title, c.title);
      const score = kw + ent * 2 + sim * 3;
      if (score > bestScore) {
        bestScore = score;
        best = c;
      }
    }
    if (best) {
      best.items.push({
        ...social,
        platform: /youtube/.test(social.url) ? "youtube" : "twitter",
      });
    }
  }

  return clusters;
}

function storyDedupeKey(report) {
  if (!report?.article_url) return normalizeStoryKey(report?.title || "");
  try {
    const u = new URL(report.article_url);
    return `${u.hostname}${u.pathname}`.toLowerCase();
  } catch {
    return normalizeStoryKey(report.title || "");
  }
}

function sortNewsFirst(a, b) {
  if (b.outlet_count !== a.outlet_count) return b.outlet_count - a.outlet_count;
  if (b.tier1_outlet_count !== a.tier1_outlet_count) return b.tier1_outlet_count - a.tier1_outlet_count;
  if (b.twitter_mentions !== a.twitter_mentions) return b.twitter_mentions - a.twitter_mentions;
  if (b.youtube_mentions !== a.youtube_mentions) return b.youtube_mentions - a.youtube_mentions;
  return b.score - a.score;
}

/** Round 2: X first, then YouTube, outlets, tier‑1, GDELT, score */
function sortTwitterFill(a, b) {
  if (b.twitter_mentions !== a.twitter_mentions) return b.twitter_mentions - a.twitter_mentions;
  if (b.youtube_mentions !== a.youtube_mentions) return b.youtube_mentions - a.youtube_mentions;
  if (b.outlet_count !== a.outlet_count) return b.outlet_count - a.outlet_count;
  if (b.tier1_outlet_count !== a.tier1_outlet_count) return b.tier1_outlet_count - a.tier1_outlet_count;
  if (b.gdelt_mentions !== a.gdelt_mentions) return b.gdelt_mentions - a.gdelt_mentions;
  return b.score - a.score;
}

function buildClusterReport(cluster, resolvedMap, options = {}) {
  const minNewsDomains = options.minNewsDomains ?? 2;
  const articles = [];
  const twitter = [];
  const youtube = [];
  const reddit = [];
  const hn = [];
  const gdelt = [];

  for (const it of cluster.items) {
    if (it.platform === "twitter" || /x\.com|twitter\.com/i.test(it.url)) twitter.push(it);
    else if (it.platform === "youtube" || /youtube\.com|youtu\.be/i.test(it.url)) youtube.push(it);
    else if (it.platform === "reddit") {
      reddit.push(it);
      articles.push(it);
    } else if (it.platform === "hacker_news") {
      hn.push(it);
      articles.push(it);
    } else if (it.platform === "gdelt") {
      gdelt.push(it);
      articles.push(it);
    } else if (isNewsArticle(it.url) || /news\.google\.com/.test(it.url)) {
      articles.push(it);
    }
  }

  const trendingOn = [];
  if (articles.some((a) => a.platform === "news" || /news\.google/.test(a.url))) trendingOn.push("Google News");
  if (articles.some((a) => a.platform === "outlet_rss")) trendingOn.push("Major outlets");
  if (gdelt.length) trendingOn.push("Global news (GDELT)");
  if (twitter.length) trendingOn.push("Twitter/X");
  if (youtube.length) trendingOn.push("YouTube");
  if (reddit.length) trendingOn.push("Reddit");
  if (hn.length) trendingOn.push("Hacker News");

  const hasArticle = articles.some((a) => {
    if (/x\.com|twitter\.com|youtube\.com/i.test(a.url)) return false;
    const resolved = resolvedMap.get(a.url) || a.url;
    if (/news\.google\.com/.test(a.url) && resolved === a.url) return true;
    if (NEWS_PUBLISHER.test(resolved)) return true;
    return isNewsArticle(resolved) && !/\.github\.io|medium\.com\/@|\.foo\b/i.test(resolved);
  });

  if (!hasArticle) return null;

  const sortedArticles = [...articles]
    .map((a) => ({
      ...a,
      resolved: resolvedMap.get(a.url) || a.url,
    }))
    .sort((a, b) => {
      const scoreUrl = (x) => {
        let s = 0;
        if (!/news\.google\.com/.test(x.resolved)) s += 20;
        if (isMainstream(x.resolved)) s += 15;
        if (x.platform === "outlet_rss") s += 10;
        return s + (x.engagement || 0) / 100;
      };
      return scoreUrl(b) - scoreUrl(a);
    });

  const newsDomains = distinctNewsDomains(sortedArticles);
  if (newsDomains.size < minNewsDomains) return null;

  const tier1Outlets = [...newsDomains].filter((d) => TIER1.test(d)).length;

  const primary = sortedArticles[0];
  const articleUrl = primary.resolved || primary.url;
  const publisher = getDomain(articleUrl);

  /** Rank: outlet count dominates; then tier‑1 sites; then social (ties). */
  let score = 0;
  score += newsDomains.size * 1_000;
  score += tier1Outlets * 250;
  score += twitter.length * 15;
  score += youtube.length * 10;
  score += gdelt.length * 8;
  score += reddit.length * 6;
  score += hn.length * 5;
  if (isMainstream(articleUrl)) score += 40;
  if (!/news\.google\.com/.test(articleUrl)) score += 25;
  score += Math.log1p(cluster.maxEngagement) * 3;
  score += trendingOn.length * 4;
  if (cluster.published) {
    const age = Math.max((Date.now() - cluster.published) / 3600000, 1);
    score += 6 * Math.exp(-age / 48);
  }
  score += reelHooks(cluster.title).length * 2;

  const verification =
    newsDomains.size >= 2
      ? `✓ ${newsDomains.size} news sites · ${tier1Outlets} tier‑1`
      : `✓ ${newsDomains.size} news site · ${tier1Outlets} tier‑1`;

  return {
    title: cleanTitle(primary.title),
    article_url: articleUrl,
    original_url: /news\.google\.com/.test(primary.url) ? primary.url : null,
    publisher,
    outlet_count: newsDomains.size,
    tier1_outlet_count: tier1Outlets,
    outlets: [...newsDomains].sort(),
    trending_on: trendingOn,
    verification,
    article_count: articles.length,
    twitter_mentions: twitter.length,
    youtube_mentions: youtube.length,
    gdelt_mentions: gdelt.length,
    published: cluster.published,
    score: Math.round(score * 10) / 10,
    hooks: reelHooks(cluster.title),
    engagement_label: reddit[0]?.label || (hn[0] ? `${hn[0].engagement} HN engagement` : ""),
    more_coverage: sortedArticles.slice(1, 4).map((a) => ({
      title: a.title,
      url: a.resolved || a.url,
      publisher: getDomain(a.resolved || a.url),
    })),
    twitter_samples: twitter.slice(0, 3).map((t) => ({ title: t.title, url: t.url })),
  };
}

async function run(days, topN) {
  const { start, end } = window(days);
  console.error(`\nAI News Agent v3.1 — real URLs · free sources only`);
  console.error(`Round 1: 2+ distinct news sites (agency-first). Round 2: if fewer than ${topN}, fill rest with X-first ranking.\n`);
  console.error(`Window: last ${days} day(s) (${start.toISOString().slice(0, 10)} → ${end.toISOString().slice(0, 10)} UTC)\n`);

  let raw = [];
  const fetches = [
    ["Google News + X + YouTube", () => fetchGoogle(days)],
    ["Publisher RSS (Verge, Ars, TC…)", () => fetchOutletRss(days)],
    ["GDELT global news index", () => fetchGdelt(days)],
    ["Reddit (article links)", () => fetchRedditArticles(days)],
    ["Hacker News", () => fetchHN(days)],
  ];
  await Promise.all(
    fetches.map(async ([name, fn]) => {
      try {
        const batch = await fn();
        console.error(`  ✓ ${name}: ${batch.length}`);
        raw = raw.concat(batch);
      } catch (e) {
        console.error(`  ✗ ${name}: ${e.message}`);
      }
    }),
  );

  const inWindow = raw.filter((i) => i.published && i.published >= start && i.published <= end);
  console.error(`\n  Resolving Google News → real publisher URLs…`);
  const googleUrls = inWindow.map((i) => i.url).filter((u) => /news\.google\.com/.test(u));
  const resolvedMap = await resolveBatch(googleUrls, 8);
  console.error(`  ✓ Resolved ${resolvedMap.size} links\n`);

  const clusters = clusterStories(inWindow);
  console.error(`  → ${clusters.length} story clusters\n`);

  const strict = clusters
    .map((c) => buildClusterReport(c, resolvedMap, { minNewsDomains: 2 }))
    .filter(Boolean)
    .sort(sortNewsFirst);

  const target = topN;
  const round1 = strict.slice(0, target).map((r) => ({ ...r, pick_round: 1 }));

  const used = new Set(round1.map(storyDedupeKey));

  let round2 = [];
  if (round1.length < target) {
    const loose = clusters
      .map((c) => buildClusterReport(c, resolvedMap, { minNewsDomains: 1 }))
      .filter(Boolean)
      .filter((r) => !used.has(storyDedupeKey(r)))
      .sort(sortTwitterFill);

    const preferX = loose.filter((r) => r.twitter_mentions >= 1);
    const rest = loose.filter((r) => r.twitter_mentions < 1);
    const need = target - round1.length;
    round2 = [...preferX, ...rest].slice(0, need).map((r) => ({ ...r, pick_round: 2 }));
    console.error(`  Round 1 (2+ news sites): ${round1.length} · Round 2 (X-priority fill): ${round2.length}\n`);
  } else {
    console.error(`  Round 1 (2+ news sites): ${round1.length}\n`);
  }

  return [...round1, ...round2];
}

function formatReport(ranked, days, targetCount) {
  const lines = [];
  lines.push(`══ Trending AI News WITH Real Articles (last ${days} days) ══`);
  lines.push(
    `   Round 1: 2+ news sites (up to ${targetCount}). Round 2: if round 1 < ${targetCount}, fill with X-first + other tiebreakers.\n`,
  );
  for (const [i, it] of ranked.entries()) {
    const when = it.published?.toISOString().slice(0, 10) ?? "—";
    const roundTag = it.pick_round === 2 ? " [R2·X-fill]" : " [R1·news]";
    lines.push(`${String(i + 1).padStart(2)}.${roundTag} [${it.score.toFixed(1)}] ${it.title.slice(0, 66)}`);
    lines.push(`    📰 ${it.article_url}`);
    if (it.publisher) lines.push(`    🏢 ${it.publisher}`);
    lines.push(`    📊 ${it.outlet_count} outlets (${it.tier1_outlet_count} major wire/Tier‑1) · ${it.verification}`);
    lines.push(`    Trending: ${it.trending_on.join(" · ")}`);
    if (it.outlets.length) lines.push(`    📄 Also on: ${it.outlets.slice(0, 6).join(", ")}`);
    if (it.twitter_mentions) {
      lines.push(`    🐦 ${it.twitter_mentions} on X`);
      it.twitter_samples?.slice(0, 2).forEach((t) => lines.push(`       → ${t.title.slice(0, 68)}`));
    }
    if (it.youtube_mentions) lines.push(`    ▶ ${it.youtube_mentions} YouTube mention(s)`);
    if (it.more_coverage?.length) {
      lines.push(`    More:`);
      it.more_coverage.forEach((m) => lines.push(`       · ${m.publisher}: ${m.title.slice(0, 55)}`));
    }
    if (it.engagement_label) lines.push(`    💬 ${it.engagement_label}`);
    if (it.hooks?.length) lines.push(`    Reel: ${it.hooks.join(" · ")}`);
    lines.push(`    ${when}\n`);
  }
  return lines.join("\n");
}

const { values } = parseArgs({
  options: {
    days: { type: "string", short: "d", default: "7" },
    top: { type: "string", short: "n", default: "15" },
    json: { type: "boolean", default: false },
    "no-save": { type: "boolean", default: false },
  },
});

const days = Math.max(1, parseInt(values.days, 10) || 7);
const topN = parseInt(values.top, 10) || 15;
const ranked = await run(days, topN);

if (values.json) {
  console.log(JSON.stringify(ranked, null, 2));
} else {
  const text = formatReport(ranked, days, topN);
  console.log("\n" + text);
  if (!values["no-save"]) {
    const dir = join(__dir, "reports");
    mkdirSync(dir, { recursive: true });
    const path = join(dir, `latest-${days}days.txt`);
    writeFileSync(path, text, "utf8");
    console.error(`Saved → reports/latest-${days}days.txt`);
  }
}
