"""Template-based Instagram Reel content generation — no AI API calls."""

import hashlib
import re

COMPANIES = [
    "OpenAI",
    "Google",
    "Meta",
    "Microsoft",
    "Apple",
    "Amazon",
    "Anthropic",
    "Nvidia",
    "Tesla",
    "DeepMind",
    "Mistral",
    "Cohere",
    "Stability AI",
    "Runway",
]

VERBS = ["launched", "unveiled", "released", "announced", "introduced"]
IMPACTS = [
    "matters for how people use AI day to day",
    "could influence the next wave of AI products",
    "is getting attention across the AI world",
    "could shape what teams build next",
]
ACTIONS = ["shipped a major update", "made a notable move", "rolled out a new release"]


def _seed(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest(), 16)


def extract_company(title: str) -> str:
    for company in COMPANIES:
        if company.lower() in title.lower():
            return company
    words = re.findall(r"\b[A-Z][a-zA-Z]+\b", title)
    return words[0] if words else "AI"


def _title_short(title: str, max_len: int = 60) -> str:
    t = title.strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 3].rsplit(" ", 1)[0] + "..."


def _extract_topic(title: str) -> str:
    lower = title.lower()
    for kw in ("gpt", "claude", "gemini", "llm", "regulation", "funding", "chip", "model"):
        if kw in lower:
            return kw.upper() if kw in ("gpt", "llm") else kw.title()
    return _title_short(title, 40)


def _story_topic(story: dict) -> str:
    topic = (story.get("ai_topic") or "").strip().lower()
    if topic:
        mapping = {
            "general": "AI",
            "product": "Product",
            "policy": "Policy",
            "hardware": "Hardware",
            "research": "Research",
            "business": "Business",
            "consumer": "Consumer AI",
            "culture": "Culture",
        }
        return mapping.get(topic, topic.title())
    return _extract_topic(story.get("title") or "")


def generate_hook(story: dict) -> str:
    title = story.get("title") or "AI news"
    company = extract_company(title)
    topic = _story_topic(story)
    title_short = _title_short(title)
    source_count = int(story.get("source_count", 1) or 1)
    idx = _seed(title) % 6
    topic_prefix = f"{topic}: " if story.get("ai_topic") else ""
    coverage_note = (
        "It's showing up across several outlets"
        if source_count >= 3
        else "It's getting attention from more than one source"
        if source_count == 2
        else "It is a single-source story worth a careful look"
    )

    templates = [
        f"{topic_prefix}{company} just {VERBS[_seed(title + 'v') % len(VERBS)]} a move that {IMPACTS[_seed(title + 'i') % len(IMPACTS)]}",
        f"{topic_prefix}Today in AI: {title_short}",
        f"{topic_prefix}Why {topic} matters this week",
        f"{topic_prefix}The {topic} story people are following right now",
        f"{topic_prefix}{company} {ACTIONS[_seed(title + 'a') % len(ACTIONS)]} and the context matters",
        f"{topic_prefix}{coverage_note}: {title_short}",
    ]
    hook = templates[idx]
    words = hook.split()
    if len(words) > 15:
        hook = " ".join(words[:15])
    return hook


def generate_caption(story: dict) -> str:
    title = story.get("title") or ""
    summary = (story.get("summary") or "").strip()
    sources = story.get("sources") or []
    topic = _story_topic(story)
    source_note = ", ".join(sources[:3]) if sources else "multiple outlets"

    if summary:
        what = summary if len(summary) < 200 else summary[:197] + "..."
    else:
        what = title

    para1 = f"📰 {what}"
    para2 = (
        f"This {topic.lower()} story is getting attention across {source_note} and is worth following "
        "if you want the clearest AI updates without the noise."
    )
    para3 = "Why it matters: these are the stories most likely to shape the tools, policies, and products people will actually notice."
    cta = "Follow for clear AI updates that stay focused on what matters."

    caption = f"{para1}\n\n{para2}\n\n{para3}\n\n{cta}"
    words = caption.split()
    if len(words) > 150:
        caption = " ".join(words[:150])
    return caption


def _story_hashtags(story: dict) -> list[str]:
    title = (story.get("title") or "").lower()
    tags = ["#AI", "#ArtificialIntelligence", "#Tech", "#Technology", "#AINews"]
    extra_map = [
        ("openai", "#OpenAI"),
        ("gpt", "#ChatGPT"),
        ("claude", "#Claude"),
        ("gemini", "#Gemini"),
        ("anthropic", "#Anthropic"),
        ("nvidia", "#Nvidia"),
        ("regulation", "#AIRegulation"),
        ("funding", "#Startup"),
        ("startup", "#AIStartup"),
        ("robot", "#Robotics"),
        ("chip", "#AIChips"),
        ("llm", "#LLM"),
        ("agent", "#AIAgents"),
        ("safety", "#AISafety"),
        ("microsoft", "#Microsoft"),
        ("google", "#Google"),
        ("meta", "#Meta"),
        ("mistral", "#Mistral"),
        ("video", "#GenerativeAI"),
        ("model", "#AIModels"),
    ]
    for needle, tag in extra_map:
        if needle in title and tag not in tags:
            tags.append(tag)
    filler = [
        "#MachineLearning",
        "#DeepLearning",
        "#Innovation",
        "#FutureTech",
        "#TechNews",
        "#News",
        "#AIUpdates",
        "#TechTok",
    ]
    for tag in filler:
        if len(tags) >= 25:
            break
        if tag not in tags:
            tags.append(tag)
    return tags[:25]


def generate_hashtags(story: dict) -> str:
    return " ".join(_story_hashtags(story))


def generate_reel_content(story: dict) -> dict:
    """Attach hook, caption, hashtags to a story dict (in place)."""
    story["hook"] = generate_hook(story)
    story["caption"] = generate_caption(story)
    story["hashtags"] = generate_hashtags(story)
    return story
