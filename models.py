from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Video:
    id: str
    title: str
    channel: str
    url: str
    published_at: datetime
    transcript: str | None = None


@dataclass
class DigestItem:
    video: Video
    summary: str
    insights: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
