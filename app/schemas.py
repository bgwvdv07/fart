from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import KeyStrategy


class FeedCreate(BaseModel):
    url: str


class FeedRead(BaseModel):
    id: int
    url: str
    title: str | None = None
    last_checked_at: datetime | None = None
    next_check_at: datetime | None = None
    error_count: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ItemRead(BaseModel):
    id: int
    feed_id: int
    url: str | None = None
    title: str | None = None
    summary: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None
    relevance_score: float | None = None
    topic: str | None = None
    is_processed: bool

    model_config = ConfigDict(from_attributes=True)


class FeedUpdateStrategy(BaseModel):
    key_strategy: KeyStrategy