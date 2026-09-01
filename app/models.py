from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column

from sqlalchemy import Enum as SqlEnum
import enum
from datetime import datetime
from app.db import Base

class KeyStrategy(str, enum.Enum):
    DEFAULT = "default"          # GUID → URL → hash
    FORCE_URL = "force_url"      # Always use URL-based key
    FORCE_HASH = "force_hash"    # Always use hash(title+summary)

class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    site_url: Mapped[str | None] = mapped_column(String, nullable=True)

    etag: Mapped[str | None] = mapped_column(String, nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String, nullable=True)

    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    avg_interval_sec: Mapped[float | None] = mapped_column(Float, nullable=True)

    error_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    key_strategy: Mapped[KeyStrategy] = mapped_column(
        SqlEnum(KeyStrategy), default=KeyStrategy.DEFAULT, nullable=False
    )

    items: Mapped[list["Item"]] = relationship("Item", back_populates="feed")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    feed_id: Mapped[int] = mapped_column(ForeignKey("feeds.id"), nullable=False, index=True)
    entry_key: Mapped[str] = mapped_column(String, nullable=False)  # GUID / URL / hash
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    author: Mapped[str | None] = mapped_column(String, nullable=True)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    feed: Mapped["Feed"] = relationship("Feed", back_populates="items")

    __table_args__ = (
        UniqueConstraint("feed_id", "entry_key", name="uq_feed_entry_key"),
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "NEW_ITEM"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)