import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

AI_QUERY = (
    '(AI OR ChatGPT OR OpenAI OR Claude OR Gemini OR Anthropic OR Sora OR '
    '"artificial intelligence" OR robot OR humanoid OR deepfake OR Copilot)'
)

REDDIT_SUBREDDITS = [
    "ChatGPT",
    "singularity",
    "artificial",
    "OpenAI",
    "Futurology",
    "technology",
]

HN_QUERY = "AI OR artificial intelligence OR machine learning OR LLM OR OpenAI OR Anthropic"

TOP_N = int(os.getenv("TOP_N", "15"))
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "").strip()


def window(days: int) -> tuple[datetime, datetime]:
    if days < 1:
        raise ValueError("days must be >= 1")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return start, end


def window_epoch(days: int) -> int:
    start, _ = window(days)
    return int(start.timestamp())
