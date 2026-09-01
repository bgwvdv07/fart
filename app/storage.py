from datetime import datetime, timedelta
from typing import Iterable, List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.rss_parser import ParsedItem


def insert_parsed_items(
    db: Session,
    feed: models.Feed,
    parsed_items: Iterable[ParsedItem],
) -> List[models.Item]:
    created: List[models.Item] = []

    for pi in parsed_items:
        item = models.Item(
    feed_id=feed.id,
    entry_key=pi.entry_key,
    url=pi.url,
    title=pi.title,
    author=pi.author,
    summary=pi.summary,
    content=pi.content,
    published_at=pi.published_at,
    image_url=pi.image_url,
    )
        try:
            with db.begin_nested():
                db.add(item)
                db.flush()
            created.append(item)
        except IntegrityError:
            continue

    return created


def get_due_feeds(db: Session, now: datetime, limit: int = 100):
    stmt = (
        select(models.Feed)
        .where(models.Feed.is_active == True)
        .where(
            (models.Feed.next_check_at.is_(None)) |
            (models.Feed.next_check_at <= now)
        )
        .order_by(models.Feed.next_check_at.asc())
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()

def update_feed_state_on_success(
    db: Session,
    feed: models.Feed,
    now: datetime,
    etag: str | None,
    last_modified: str | None,
    observed_interval_sec: int | None = None,
) -> None:
    feed.last_checked_at = now
    feed.etag = etag
    feed.last_modified = last_modified
    feed.error_count = 0
    feed.next_check_at = now + timedelta(minutes=15)
    db.add(feed)

def update_feed_state_on_error(
    db: Session,
    feed: models.Feed,
    now: datetime,
) -> None:
    feed.last_checked_at = now
    feed.error_count = (feed.error_count or 0) + 1
    feed.next_check_at = now + timedelta(minutes=15)
    db.add(feed)


def enqueue_new_item_events(db: Session, items: List[models.Item]) -> None:
    # Placeholder: no-op for now until you add an events table/queue
    return