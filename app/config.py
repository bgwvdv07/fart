from typing import List

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg2://rss_user:Wy137Lee*@localhost/rss_monitor"
    rss_user_agent: str = "MyRSSBot/0.1 (+https://example.com/contact)"
    article_user_agent: str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    max_feeds_per_run: int = 100
    poll_interval_seconds: int = 60
    min_feed_interval_seconds: int = 300
    max_feed_interval_seconds: int = 86400
    scoring_batch_size: int = 100
    scoring_interval_seconds: int = 60
    allowed_origins: List[AnyHttpUrl] = []


settings = Settings()
