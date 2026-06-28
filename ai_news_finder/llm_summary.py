"""Optional local LLM summarization for richer article briefs."""

from __future__ import annotations

import os
import re
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")


def _running_in_kaggle() -> bool:
    return bool(
        os.getenv("KAGGLE_KERNEL_RUN_TYPE")
        or os.getenv("KAGGLE_URL_BASE")
        or os.path.exists("/kaggle/working")
    )


def should_use_summary_model() -> bool:
    """Return True when the optional local summarizer should be used."""
    flag = os.getenv("AI_NEWS_USE_SUMMARY_MODEL", "auto").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    if flag in {"1", "true", "yes", "on"}:
        return True
    return _running_in_kaggle()


def summary_model_name() -> str:
    return os.getenv("AI_NEWS_SUMMARY_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")


def _clean_generated_text(text: str) -> str:
    clean = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    clean = re.sub(r"^\s*(summary|answer)\s*:\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean).strip()
    clean = re.sub(r"\bContinue reading\b.*$", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\bRead more\b.*$", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\s+([,.;:!?])", r"\1", clean)
    return clean


warnings.filterwarnings("ignore", message="`torch_dtype` is deprecated!")
warnings.filterwarnings("ignore", message="The following generation flags are not valid and may be ignored:*")


@dataclass
class LLMStorySummarizer:
    model_name: str = field(default_factory=summary_model_name)
    _tokenizer: Any | None = field(default=None, init=False, repr=False)
    _model: Any | None = field(default=None, init=False, repr=False)

    def available(self) -> bool:
        try:
            import transformers  # noqa: F401
            import torch  # noqa: F401
        except Exception:
            return False
        return True

    def _load(self) -> tuple[Any | None, Any | None]:
        if self._tokenizer is not None and self._model is not None:
            return self._tokenizer, self._model
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except Exception:
            return None, None

        load_attempts = [
            {
                "dtype": torch.float16 if torch.cuda.is_available() else torch.float32,
                "device_map": "auto" if torch.cuda.is_available() else None,
            },
            {
                "dtype": torch.float32,
                "device_map": None,
            },
        ]

        try:
            tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
        except Exception:
            return None, None

        for kwargs in load_attempts:
            try:
                model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    trust_remote_code=True,
                    **{k: v for k, v in kwargs.items() if v is not None},
                )
                self._tokenizer = tokenizer
                self._model = model
                return tokenizer, model
            except Exception:
                continue

        return None, None

    def rewrite_summary(
        self,
        *,
        title: str,
        sources: list[str],
        article_text: str,
        existing_summary: str = "",
    ) -> str:
        tokenizer, model = self._load()
        if tokenizer is None or model is None or not article_text.strip():
            return ""

        source_text = ", ".join([s for s in sources if s]) if sources else "unknown sources"
        prompt = (
            "You are editing a premium AI news newsletter.\n"
            "Rewrite the story into 4 to 6 concise sentences, about 120 to 180 words.\n"
            "Keep the facts accurate. Remove duplicated wording, typos, and boilerplate.\n"
            "Do not invent anything. Do not add bullets, headings, or emojis.\n"
            "If the material is thin, say that plainly.\n\n"
            f"Title: {title}\n"
            f"Sources: {source_text}\n"
        )
        if existing_summary:
            prompt += f"Existing summary: {existing_summary}\n"
        prompt += f"Article material:\n{article_text[:7000]}\n\nSummary:"

        try:
            messages = [
                {"role": "system", "content": "You are a careful newsroom editor."},
                {"role": "user", "content": prompt},
            ]
            if hasattr(tokenizer, "apply_chat_template"):
                input_text = tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            else:
                input_text = prompt
            inputs = tokenizer(
                input_text,
                return_tensors="pt",
                truncation=True,
                max_length=4096,
            )
            try:
                device = next(model.parameters()).device
                inputs = {k: v.to(device) for k, v in inputs.items()}
            except Exception:
                pass
            output = model.generate(
                **inputs,
                max_new_tokens=220,
                do_sample=False,
                repetition_penalty=1.08,
                pad_token_id=getattr(tokenizer, "eos_token_id", None),
            )
            prompt_len = inputs["input_ids"].shape[-1]
            generated = output[0][prompt_len:]
            text = tokenizer.decode(generated, skip_special_tokens=True)
        except Exception:
            return ""

        return _clean_generated_text(text)


@lru_cache(maxsize=1)
def get_llm_summarizer() -> LLMStorySummarizer | None:
    if not should_use_summary_model():
        return None
    summarizer = LLMStorySummarizer()
    if not summarizer.available():
        return None
    return summarizer
