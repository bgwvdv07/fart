from datetime import datetime
from typing import List
from sqlalchemy.orm import Session
from app.db import SessionLocal
from sqlalchemy import select
from app import models
from app.config import settings

def fetch_items_to_score(db: Session, limit: int) -> List[models.Item]:
    stmt = (
        select(models.Item)
        .where(models.Item.relevance_score.is_(None))
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def compute_relevance_score(item: models.Item) -> float:
    """
    Placeholder: implement your actual model here.
    Could use item.title, summary, content, feed metadata, etc.
    """
    # Example: dummy constant; replace with real model output.
    return 0.5


def score_batch(db: Session, items: List[models.Item]) -> None:
    now = datetime.utcnow()
    for item in items:
        score = compute_relevance_score(item)
        item.relevance_score = score
        item.is_processed = True
        db.add(item)


def scoring_job() -> None:
    """
    Optional APScheduler job: batch-score items.
    """
    db: Session = SessionLocal()
    try:
        items = fetch_items_to_score(db, settings.scoring_batch_size)
        if not items:
            return
        score_batch(db, items)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()