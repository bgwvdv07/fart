from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db import get_db
from app import models, schemas

router = APIRouter()


class PaginatedItemsResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[schemas.ItemRead]


@router.get("/", response_model=PaginatedItemsResponse)
def list_items(
    feed_id: int | None = Query(None),
    min_score: float | None = Query(None, ge=0.0),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    base_stmt = select(models.Item)

    if feed_id is not None:
        base_stmt = base_stmt.where(models.Item.feed_id == feed_id)

    if min_score is not None:
        base_stmt = base_stmt.where(models.Item.relevance_score >= min_score)

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    page_stmt = (
        base_stmt
        .order_by(models.Item.published_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = db.execute(page_stmt).scalars().all()

    return PaginatedItemsResponse(
        total=total,
        offset=offset,
        limit=limit,
        items=rows,
    )