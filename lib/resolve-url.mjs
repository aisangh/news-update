const UA = "ai-news-agent/3.1";
const cache = new Map();

/** Follow redirects to get the real publisher URL (esp. Google News). */
export async function resolveArticleUrl(url) {
  if (!url) return url;
  if (cache.has(url)) return cache.get(url);
  if (!/news\.google\.com|google\.com\/url/i.test(url)) {
    cache.set(url, url);
    return url;
  }
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 10000);
    const res = await fetch(url, {
      method: "GET",
      redirect: "follow",
      headers: { "User-Agent": UA, Accept: "text/html" },
      signal: ctrl.signal,
    });
    clearTimeout(t);
    const final = res.url && !res.url.includes("news.google.com") ? res.url : url;
    cache.set(url, final);
    return final;
  } catch {
    cache.set(url, url);
    return url;
  }
}

export async function resolveBatch(urls, concurrency = 6) {
  const unique = [...new Set(urls.filter((u) => /news\.google\.com/.test(u)))];
  const out = new Map();
  for (let i = 0; i < unique.length; i += concurrency) {
    const chunk = unique.slice(i, i + concurrency);
    await Promise.all(
      chunk.map(async (u) => out.set(u, await resolveArticleUrl(u))),
    );
  }
  return out;
}

export function clearResolveCache() {
  cache.clear();
}
