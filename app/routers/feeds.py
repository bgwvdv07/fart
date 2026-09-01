from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import get_db
from app import models, schemas

router = APIRouter()

@router.get("/", response_model=list[schemas.FeedRead])
def list_feeds(db: Session = Depends(get_db)):
    feeds = db.execute(select(models.Feed)).scalars().all()
    return feeds

@router.post("/", response_model=schemas.FeedRead)
def add_feed(payload: schemas.FeedCreate, db: Session = Depends(get_db)):
    existing = db.execute(
        select(models.Feed).where(models.Feed.url == payload.url)
    ).scalars().first()

    if existing:
        raise HTTPException(status_code=400, detail="Feed already exists")

    feed = models.Feed(url=payload.url, is_active=True)
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed

@router.patch("/{feed_id}/strategy", response_model=schemas.FeedRead)
def update_feed_strategy(
    feed_id: int,
    payload: schemas.FeedUpdateStrategy,
    db: Session = Depends(get_db),
):
    feed = db.execute(
        select(models.Feed).where(models.Feed.id == feed_id)
    ).scalars().first()

    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    feed.key_strategy = payload.key_strategy
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed