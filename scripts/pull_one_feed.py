# scripts/poll_one_feed.py

import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import SessionLocal, Base, engine
from app import models
from app import rss_fetcher, rss_parser, storage

# Ensure tables exist
Base.metadata.create_all(bind=engine)


async def poll_single_feed(feed_url: str) -> None:
    db: Session = SessionLocal()
    try:
        # Ensure feed row exists
        stmt = select(models.Feed).where(models.Feed.url == feed_url)
        feed = db.execute(stmt).scalars().first()
        if not feed:
            feed = models.Feed(url=feed_url, is_active=True)
            db.add(feed)
            db.commit()
            db.refresh(feed)

        now = datetime.utcnow()
        result = await rss_fetcher.fetch_feed(
            url=feed.url,
            etag=feed.etag,
            last_modified=feed.last_modified,
        )

        if result.status_code == 304:
            print("Feed not modified since last check")
            storage.update_feed_state_on_success(
                db,
                feed,
                now,
                result.etag,
                result.last_modified,
                observed_interval_sec=None,
            )
            db.commit()
            return

        if result.status_code != 200 or not result.content:
            print(f"Error fetching feed: status={result.status_code}")
            storage.update_feed_state_on_error(db, feed, now)
            db.commit()
            return

        parsed_items = rss_parser.parse_feed(result.content)
        new_items = storage.insert_parsed_items(db, feed, parsed_items)
        storage.enqueue_new_item_events(db, new_items)

        print(f"Parsed {len(parsed_items)} items, {len(new_items)} new")

        storage.update_feed_state_on_success(
            db,
            feed,
            now,
            result.etag,
            result.last_modified,
            observed_interval_sec=None,
        )
        db.commit()

        for item in new_items[:5]:
            print("NEW:", item.id, item.title, "score:", item.relevance_score)

    finally:
        db.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.poll_one_feed <feed_url>")
        raise SystemExit(1)
    url = sys.argv[1]
    asyncio.run(poll_single_feed(url))