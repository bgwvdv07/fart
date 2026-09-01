from datetime import datetime
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app import storage
from app import rss_fetcher, rss_parser
from app.config import settings

async def poll_feeds_job() -> None:
    print("REAL poll_feeds_job started")
    now = datetime.utcnow()
    db: Session = SessionLocal()

    try:
        feeds = storage.get_due_feeds(db, now, settings.max_feeds_per_run)
        print("due feeds:", len(feeds))

        for feed in feeds:
            try:
                print("checking feed:", feed.url)

                result = await rss_fetcher.fetch_feed(
                    url=feed.url,
                    etag=feed.etag,
                    last_modified=feed.last_modified,
                )
                print("status:", result.status_code)

                if result.status_code == 304:
                    storage.update_feed_state_on_success(
                        db, feed, now, result.etag, result.last_modified
                    )
                    db.commit()
                    continue

                if result.status_code != 200 or not result.content:
                    storage.update_feed_state_on_error(db, feed, now)
                    db.commit()
                    continue

                parsed_items = rss_parser.parse_feed(
                    result.content,
                    key_strategy=getattr(feed, "key_strategy", "default"),
                )
                print("parsed items:", len(parsed_items))

                if parsed_items:
                    print("first parsed image_url:", parsed_items[0].image_url)

                new_items = storage.insert_parsed_items(db, feed, parsed_items)
                print("new items inserted:", len(new_items))

                storage.enqueue_new_item_events(db, new_items)
                storage.update_feed_state_on_success(
                    db, feed, now, result.etag, result.last_modified
                )

                db.commit()

            except Exception as e:
                print(f"feed failed: {feed.url} -> {repr(e)}")
                db.rollback()
                try:
                    storage.update_feed_state_on_error(db, feed, now)
                    db.commit()
                except Exception:
                    db.rollback()
                continue

        print("poll_feeds_job finished")

    finally:
        db.close()