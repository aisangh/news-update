"""AI keyword filter for raw stories."""

AI_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "large language model",
    "llm",
    "gpt",
    "claude",
    "gemini",
    "mistral",
    "openai",
    "anthropic",
    "google deepmind",
    "meta ai",
    "nvidia ai",
    "chatgpt",
    "generative ai",
    "neural network",
    "diffusion model",
    "transformer model",
    "ai agent",
    "agentic ai",
    "ai regulation",
    "ai safety",
    "reinforcement learning",
    "robotics ai",
    "ai chip",
    "ai model",
    "ai tool",
    "foundation model",
    "multimodal",
    "fine-tuning",
    "ai startup",
    "ai funding",
    "ai research",
    "copilot",
    "stable diffusion",
    "midjourney",
    "sora",
    "runway ml",
]

FINANCE_EXCLUSION_KEYWORDS = [
    "stock",
    "stocks",
    "share price",
    "shares",
    "market cap",
    "nasdaq",
    "nyse",
    "wall street",
    "earnings",
    "revenue",
    "guidance",
    "trading",
    "trader",
    "traders",
    "investor",
    "investors",
    "investment",
    "investments",
    "analyst",
    "analysts",
    "ipo",
    "dividend",
    "bullish",
    "bearish",
    "hedge fund",
    "portfolio",
    "valuation",
    "quarter",
    "quarterly",
]

EXCLUSION_KEYWORDS = [
    "horoscope",
    "zodiac",
    "astrology",
    "birthdate",
    "lucky number",
    "today's forecast",
    "spiritual",
    "tarot",
    "predict your",
    "what's your sign",
]


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def _story_text(story: dict) -> str:
    title = story.get("title") or ""
    summary = story.get("summary") or ""
    return f"{title} {summary}".lower()


def filter_ai_stories(stories: list[dict]) -> list[dict]:
    """Keep stories whose title + summary match at least one AI keyword, excluding non-AI content."""
    filtered: list[dict] = []
    for story in stories:
        text = _story_text(story)

        if _contains_any(text, EXCLUSION_KEYWORDS):
            continue

        if _contains_any(text, FINANCE_EXCLUSION_KEYWORDS):
            continue

        if _contains_any(text, AI_KEYWORDS):
            filtered.append(story)
    return filtered
