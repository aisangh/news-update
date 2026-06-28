"""Optional Hugging Face semantic ranking for AI News Finder.

The ranker is designed for Kaggle-style notebook runs where you can afford a
small local embedding model, but it falls back cleanly when the dependency is
missing or disabled.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

POSITIVE_PROFILES: dict[str, str] = {
    "general": "major AI news story that a general audience would care about",
    "product": "AI product launch or major consumer feature update with wide impact",
    "policy": "AI policy, regulation, safety, or government decision with broad consequences",
    "hardware": "AI chip, hardware, device, or infrastructure story with market impact",
    "research": "AI research breakthrough or model release that matters to developers and the public",
    "business": "major AI business move, partnership, funding, or deal",
    "consumer": "consumer AI feature or app update people will actually use",
    "culture": "AI story with cultural, creative, or public-interest significance",
}

NEGATIVE_PROFILES: dict[str, str] = {
    "press_release": "press release, promotional announcement, or marketing copy",
    "academic": "niche academic paper, abstract, or technical benchmark without broad relevance",
    "finance_noise": "stock market, earnings, valuation, or investor-only AI trading story",
    "local_training": "local training session, classroom exercise, workshop, or generic adoption story",
    "newsletter_noise": "newsletter roundup, podcast promotion, or opinion piece about AI",
}


def _running_in_kaggle() -> bool:
    return bool(
        os.getenv("KAGGLE_KERNEL_RUN_TYPE")
        or os.getenv("KAGGLE_URL_BASE")
        or os.path.exists("/kaggle/working")
    )


def should_use_hf_ranker() -> bool:
    """Return True when the optional Hugging Face ranker should be used."""
    flag = os.getenv("AI_NEWS_USE_HF")
    if flag == "0":
        return False
    if flag == "1":
        return True
    return _running_in_kaggle()


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return math.sqrt(sum(x * x for x in a)) or 1.0


def _cosine(a: list[float], b: list[float]) -> float:
    return _dot(a, b) / (_norm(a) * _norm(b))


@dataclass
class HFStoryRanker:
    model_name: str = field(default_factory=lambda: os.getenv(
        "AI_NEWS_HF_MODEL",
        "sentence-transformers/all-mpnet-base-v2",
    ))
    _model: Any | None = field(default=None, init=False, repr=False)
    _profile_embeddings: dict[str, list[float]] = field(default_factory=dict, init=False, repr=False)

    def available(self) -> bool:
        try:
            import sentence_transformers  # noqa: F401
        except Exception:
            return False
        return True

    def _load_model(self) -> Any | None:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except Exception:
            return None
        self._model = SentenceTransformer(self.model_name)
        return self._model

    def _embed(self, text: str) -> list[float] | None:
        model = self._load_model()
        if model is None:
            return None
        vector = model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
        return [float(x) for x in vector]

    def _profile_embedding(self, key: str, text: str) -> list[float] | None:
        if key in self._profile_embeddings:
            return self._profile_embeddings[key]
        vector = self._embed(text)
        if vector is not None:
            self._profile_embeddings[key] = vector
        return vector

    def story_text(self, story: dict) -> str:
        parts = [
            story.get("title") or "",
            story.get("summary") or "",
            story.get("detailed_summary") or "",
            " ".join(story.get("sources") or []),
        ]
        return " ".join(part for part in parts if part).strip()

    def _similarity(self, text: str, prompt: str, prompt_key: str) -> float:
        story_vec = self._embed(text)
        if story_vec is None:
            return 0.0
        prompt_vec = self._profile_embedding(prompt_key, prompt)
        if prompt_vec is None:
            return 0.0
        return max(-1.0, min(1.0, _cosine(story_vec, prompt_vec)))

    def story_score(self, story: dict) -> float:
        text = self.story_text(story)
        if not text:
            return 0.0

        positive = max(
            self._similarity(text, prompt, f"pos:{key}")
            for key, prompt in POSITIVE_PROFILES.items()
        )
        negative = max(
            self._similarity(text, prompt, f"neg:{key}")
            for key, prompt in NEGATIVE_PROFILES.items()
        )
        source_count = max(
            int(story.get("source_count", 0) or 0),
            len([s for s in (story.get("sources") or []) if s]),
        )
        source_bonus = min(source_count, 3) * 0.03
        score = (positive * 0.78) - (negative * 0.38) + source_bonus
        return max(0.0, min(1.0, score))

    def topic_label(self, story: dict) -> str:
        text = self.story_text(story)
        if not text:
            return "general"
        best_key = "general"
        best_score = -1.0
        for key, prompt in POSITIVE_PROFILES.items():
            score = self._similarity(text, prompt, f"topic:{key}")
            if score > best_score:
                best_score = score
                best_key = key
        return best_key

    def annotate(self, stories: list[dict]) -> None:
        for story in stories:
            story["hf_score"] = round(self.story_score(story), 3)
            story["ai_topic"] = self.topic_label(story)


@lru_cache(maxsize=1)
def get_hf_ranker() -> HFStoryRanker | None:
    if not should_use_hf_ranker():
        return None
    ranker = HFStoryRanker()
    if not ranker.available():
        return None
    return ranker
