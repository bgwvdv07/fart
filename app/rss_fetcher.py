from typing import Optional
from datetime import datetime
import httpx
from app.config import settings

class FetchResult:
    def __init__(
        self,
        status_code: int,
        content: Optional[bytes],
        etag: Optional[str],
        last_modified: Optional[str],
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.etag = etag
        self.last_modified = last_modified


async def fetch_feed(
    url: str,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
    timeout: float = 10.0,
) -> FetchResult:
    headers = {
        "User-Agent": settings.rss_user_agent,
    }
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=headers)

    new_etag = resp.headers.get("ETag")
    new_last_modified = resp.headers.get("Last-Modified")

    if resp.status_code == 304:
        return FetchResult(status_code=304, content=None, etag=new_etag, last_modified=new_last_modified)

    return FetchResult(
        status_code=resp.status_code,
        content=resp.content,
        etag=new_etag,
        last_modified=new_last_modified,
    )