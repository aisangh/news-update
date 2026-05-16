const UA = "ai-news-agent/3.1";

/** GDELT DOC 2.0 — free global news index, no API key */
export async function fetchGdelt(days) {
  const end = new Date();
  const start = new Date(end.getTime() - days * 86400000);
  const fmt = (d) =>
    d.toISOString().replace(/[-:T]/g, "").slice(0, 14);
  const query = encodeURIComponent(
    '(artificial intelligence OR "machine learning" OR ChatGPT OR OpenAI OR Claude OR Gemini OR Anthropic OR Sora OR humanoid robot)',
  );
  const url =
    `https://api.gdeltproject.org/api/v2/doc/doc?query=${query}` +
    `&mode=artlist&maxrecords=80&format=json` +
    `&STARTDATETIME=${fmt(start)}&ENDDATETIME=${fmt(end)}`;

  try {
    const res = await fetch(url, { headers: { "User-Agent": UA } });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.articles || []).map((a) => {
      const published = a.seendate
        ? new Date(
            `${a.seendate.slice(0, 4)}-${a.seendate.slice(4, 6)}-${a.seendate.slice(6, 8)}T${a.seendate.slice(9, 11)}:${a.seendate.slice(11, 13)}:00Z`,
          )
        : null;
      return {
        title: (a.title || "").trim(),
        url: a.url || "",
        platform: "gdelt",
        published,
        engagement: 0,
        domain: (a.domain || "").replace(/^www\./, ""),
        sourceCountry: a.sourcecountry || "",
      };
    });
  } catch {
    return [];
  }
}
