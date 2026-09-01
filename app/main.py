from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger


from app.logging_config import setup_logging
from app.config import settings
from app.db import Base, engine
from app import scoring
from app.scheduler import poll_feeds_job
from app.routers import feeds, items
from datetime import datetime

scheduler = AsyncIOScheduler()

setup_logging()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="RSS Monitor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    scheduler.add_job(
    poll_feeds_job,
    "interval",
    seconds=60,
    id="poll_feeds",
    replace_existing=True,
    next_run_time=datetime.now(),
)
    scheduler.add_job(
        scoring.scoring_job,
        IntervalTrigger(seconds=settings.scoring_interval_seconds),
        id="scoring_job",
        replace_existing=True,
    )
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()

app.include_router(feeds.router, prefix="/api/feeds", tags=["feeds"])
app.include_router(items.router, prefix="/api/items", tags=["items"])