from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    published: datetime | None
    engagement: int = 0
    engagement_label: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)

    def virality_key(self) -> str:
        return self.url.split("?")[0].rstrip("/").lower()
