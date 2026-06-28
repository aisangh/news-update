"""Template-based social copy generation — no AI API calls."""

import re

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


def generate_caption(story: dict) -> str:
    title = story.get("title") or ""
    summary = (story.get("summary") or "").strip()
    detailed = (story.get("detailed_summary") or "").strip()
    sources = story.get("sources") or []
    source_count = int(story.get("source_count", len(sources) or 1) or 1)
    topic = _story_topic(story)
    source_note = ", ".join(sources[:3]) if sources else "multiple outlets"
    if len(sources) > 3:
        source_note += f" + {len(sources) - 3} more"

    if detailed:
        what = detailed if len(detailed) < 220 else detailed[:217] + "..."
    elif summary:
        what = summary if len(summary) < 220 else summary[:217] + "..."
    else:
        what = title

    if source_count >= 3:
        context = f"This is a cross-checked {topic.lower()} story with coverage from {source_note}."
        why = "That usually means the development has real momentum, not just a single-source splash."
    elif source_count == 2:
        context = f"This {topic.lower()} story appears in two outlets and is worth a closer look."
        why = "The overlap suggests there is enough signal here to treat it as more than background noise."
    else:
        context = f"This is a single-source {topic.lower()} story, so the details matter."
        why = "Single-source stories can still be important, but they deserve a careful read before they spread."
    lead = f"📰 {what}"
    closing = "Follow for sharp AI coverage that stays focused on what actually changed."

    caption = f"{lead}\n\n{context}\n\n{why}\n\n{closing}"
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
    """Attach caption and hashtags to a story dict (in place)."""
    story["caption"] = generate_caption(story)
    story["hashtags"] = generate_hashtags(story)
    return story
