# app/rss_parser.py (updated parse_feed with collision logging)

from __future__ import annotations
from html import unescape
from dataclasses import dataclass
from datetime import datetime
from time import mktime
from typing import Optional, List, Dict, Tuple
import logging
import re
import feedparser
import hashlib
from app.models import KeyStrategy
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

DOMAIN_SELECTORS = {
    "nme.com": [
        ("meta[property='og:image']", "content"),
        ("meta[property='og:image:url']", "content"),
        ("meta[name='twitter:image']", "content"),
        ("meta[name='twitter:image:src']", "content"),
    ],
    "www.nme.com": [
        ("meta[property='og:image']", "content"),
        ("meta[property='og:image:url']", "content"),
        ("meta[name='twitter:image']", "content"),
        ("meta[name='twitter:image:src']", "content"),
    ],
}


LAZY_ATTRS = (
    "data-src",
    "data-original",
    "data-lazy-src",
    "data-srcset",
    "data-image",
    "data-fallback-src",
)



@dataclass
class ParsedItem:
    entry_key: str
    url: Optional[str] = None
    image_url: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    published_at: Optional[datetime] = None

def compute_entry_key(
    guid: Optional[str],
    link: Optional[str],
    title: Optional[str],
    summary: Optional[str],
    strategy: KeyStrategy = KeyStrategy.DEFAULT,
) -> str:
    """
    Derive a stable key for an entry with feed-specific strategy.

    DEFAULT: GUID → URL → hash(title+summary).
    FORCE_URL: URL → hash(title+summary).
    FORCE_HASH: hash(title+summary) only.

    This lets you override problematic feeds that reuse GUIDs or URLs [web:62][web:66].
    """
    # Compute base hash once; used by FORCE_HASH and fallbacks.
    base = (title or "") + "::" + (summary or "")
    digest = hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()

    if strategy == KeyStrategy.FORCE_HASH:
        return f"hash:{digest}"

    if strategy == KeyStrategy.FORCE_URL:
        if link:
            return f"url:{link.strip()}"
        return f"hash:{digest}"

    # DEFAULT strategy
    if guid:
        return f"guid:{guid.strip()}"

    if link:
        return f"url:{link.strip()}"

    return f"hash:{digest}"    


def _to_datetime(struct_time) -> Optional[datetime]:
    if not struct_time:
        return None
    try:
        return datetime.fromtimestamp(mktime(struct_time))
    except Exception:
        return None

def is_bad_image_url(url: str | None) -> bool:
    if not url:
        return True

    u = url.lower()
    bad_parts = [
        "cropped-",
        "site-logo",
        "favicon",
        "apple-touch-icon",
        "sprite",
        "blank.gif",
        "placeholder",
    ]
    return any(part in u for part in bad_parts)

def is_likely_browser_usable_image(url: str) -> bool:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=(5, 10),
            allow_redirects=True,
            stream=True,
        )
        resp.raise_for_status()
        content_type = (resp.headers.get("Content-Type") or "").lower()
        return content_type.startswith("image/")
    except requests.RequestException:
        return False

def parse_srcset(value: str) -> list[str]:
    urls = []
    for part in value.split(","):
        tokens = part.strip().split()
        if tokens:
            urls.append(tokens[0])
    return urls

def choose_best_image(candidates: list[str], base_url: str) -> Optional[str]:
    for raw in candidates:
        if not raw:
            continue
        url = urljoin(base_url, raw.strip())
        if url.startswith("data:"):
            continue
        if not is_bad_image_url(url):
            return url
    return None

def extract_meta_image(soup: BeautifulSoup, page_url: str) -> Optional[str]:
    selectors = [
        ("meta", {"property": "og:image"}),
        ("meta", {"property": "og:image:url"}),
        ("meta", {"name": "twitter:image"}),
        ("meta", {"name": "twitter:image:src"}),
    ]

    for tag_name, attrs in selectors:
        tag = soup.find(tag_name, attrs=attrs)
        if tag:
            content = tag.get("content")
            if content:
                url = urljoin(page_url, content.strip())
                if not is_bad_image_url(url):
                    return url
    return None
def is_feedspot_feed(parsed_feed=None, entry=None) -> bool:
    values = []

    if parsed_feed is not None:
        feed_obj = getattr(parsed_feed, "feed", {}) or {}
        values.extend([
            str(feed_obj.get("title", "")).lower(),
            str(feed_obj.get("link", "")).lower(),
            str(feed_obj.get("subtitle", "")).lower(),
        ])

    if entry is not None:
        values.extend([
            str(entry.get("author", "")).lower(),
            str(entry.get("source", "")).lower(),
            str(entry.get("summary", "")).lower()[:500],
        ])

    return any("feedspot" in v for v in values)

def extract_img_candidates_from_tag(tag, page_url: str) -> list[str]:
    candidates = []

    src = tag.get("src")
    if src:
        candidates.append(src)

    srcset = tag.get("srcset")
    if srcset:
        candidates.extend(parse_srcset(srcset))

    for attr in LAZY_ATTRS:
        val = tag.get(attr)
        if not val:
            continue
        if "srcset" in attr:
            candidates.extend(parse_srcset(val))
        else:
            candidates.append(val)

    return [urljoin(page_url, c) for c in candidates if c]

def extract_domain_specific_image(soup: BeautifulSoup, page_url: str) -> Optional[str]:
    host = urlparse(page_url).hostname or ""
    selectors = DOMAIN_SELECTORS.get(host, [])

    for selector, attr in selectors:
        tag = soup.select_one(selector)
        if not tag:
            continue
        value = tag.get(attr)
        if not value:
            continue
        url = urljoin(page_url, value.strip())
        if not is_bad_image_url(url):
            return url

    return None


def extract_article_image(page_url: str) -> Optional[str]:
    session = requests.Session()

    try:
        resp = session.get(
            page_url,
            headers=HEADERS,
            timeout=(5, 10),
            allow_redirects=True,
        )
        logger.info("article_fetch_ok", extra={
            "page_url": page_url,
            "status_code": resp.status_code,
            "final_url": resp.url,
            "content_type": resp.headers.get("Content-Type"),
        })
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("article_fetch_failed", extra={
            "page_url": page_url,
            "error": str(exc),
        })
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    domain_specific = extract_domain_specific_image(soup, resp.url)
    if domain_specific:
        logger.info("article_image_found", extra={
            "page_url": page_url,
            "method": "domain_specific",
            "image_url": domain_specific,
        })
        return domain_specific

    meta_image = extract_meta_image(soup, resp.url)
    if meta_image:
        logger.info("article_image_found", extra={
            "page_url": page_url,
            "method": "meta",
            "image_url": meta_image,
        })
        return meta_image

    for img in soup.find_all("img"):
        candidates = extract_img_candidates_from_tag(img, page_url)
        chosen = choose_best_image(candidates, page_url)
        if chosen and is_likely_browser_usable_image(chosen):
            return chosen

    for source in soup.find_all("source"):
        srcset = source.get("srcset")
        if not srcset:
            continue
        chosen = choose_best_image(parse_srcset(srcset), resp.url)
        if chosen and is_likely_browser_usable_image(chosen):
            logger.info("article_image_found", extra={
                "page_url": page_url,
                "method": "source_srcset",
                "image_url": chosen,
            })
            return chosen

    logger.info("article_image_missing", extra={
        "page_url": page_url,
        "method": "none",
    })
    return None

def extract_og_image(page_url: str) -> Optional[str]:
    try:
        resp = requests.get(
            page_url,
            headers=HEADERS,
            timeout=10,
            allow_redirects=True,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    selectors = [
        ("meta", {"property": "og:image"}),
        ("meta", {"property": "og:image:url"}),
        ("meta", {"name": "twitter:image"}),
        ("meta", {"name": "twitter:image:src"}),
    ]

    for tag_name, attrs in selectors:
        tag = soup.find(tag_name, attrs=attrs)
        if tag:
            content = tag.get("content")
            if content:
                return urljoin(page_url, content.strip())

    return None


def extract_image_url(entry, parsed_feed=None) -> Optional[str]:
    link = entry.get("link")
    feed_home = ""

    if parsed_feed is not None:
        feed_obj = getattr(parsed_feed, "feed", {}) or {}
        feed_home = feed_obj.get("link") or ""

    if link:
        link = urljoin(feed_home, link)
    title = entry.get("title", "")

    media_content = entry.get("media_content")
    if media_content:
        for media in media_content:
            url = media.get("url")
            medium = (media.get("medium") or "").lower()
            mime_type = (media.get("type") or "").lower()
            if url and (medium == "image" or mime_type.startswith("image/")) and not is_bad_image_url(url):
                logger.info("entry_image_found", extra={
                    "title": title,
                    "link": link,
                    "method": "media_content",
                    "image_url": url,
                })
                return url

    media_thumbnail = entry.get("media_thumbnail")
    if media_thumbnail:
        for item in media_thumbnail:
            url = item.get("url")
            if url and not is_bad_image_url(url):
                logger.info("entry_image_found", extra={
                    "title": title,
                    "link": link,
                    "method": "media_thumbnail",
                    "image_url": url,
                })
                return url

    enclosures = entry.get("enclosures")
    if enclosures:
        for enc in enclosures:
            href = enc.get("href") or enc.get("url")
            enc_type = (enc.get("type") or "").lower()
            if href and enc_type.startswith("image/") and not is_bad_image_url(href):
                logger.info("entry_image_found", extra={
                    "title": title,
                    "link": link,
                    "method": "enclosure",
                    "image_url": href,
                })
                return href

    if link and is_feedspot_feed(parsed_feed=parsed_feed, entry=entry):
        href = extract_article_image(link)
        if href and not is_bad_image_url(href):
            logger.info("entry_image_found", extra={
                "title": title,
                "link": link,
                "method": "article_page_feedspot_priority",
                "image_url": href,
            })
            return href

    html_candidates = []

    summary = entry.get("summary")
    if summary:
        html_candidates.append(unescape(summary))

    content = entry.get("content")
    if content:
        for part in content:
            value = part.get("value")
            if value:
                html_candidates.append(unescape(value))

    for html in html_candidates:
        soup = BeautifulSoup(html, "html.parser")
        for img in soup.find_all("img"):
            candidates = extract_img_candidates_from_tag(img, link or "")
            chosen = choose_best_image(candidates, link or "")
            if chosen:
                logger.info("entry_image_found", extra={
                    "title": title,
                    "link": link,
                    "method": "html_img",
                    "image_url": chosen,
                })
                return chosen

    itunes_image = entry.get("itunes_image")
    if isinstance(itunes_image, dict):
        href = itunes_image.get("href")
        if href and not is_bad_image_url(href):
            logger.info("entry_image_found", extra={
                "title": title,
                "link": link,
                "method": "itunes_image",
                "image_url": href,
            })
            return href

    entry_image = entry.get("image")
    if isinstance(entry_image, dict):
        href = entry_image.get("href")
        if href and not is_bad_image_url(href):
            logger.info("entry_image_found", extra={
                "title": title,
                "link": link,
                "method": "entry_image",
                "image_url": href,
            })
            return href

    if link:
        href = extract_article_image(link)
        if href and not is_bad_image_url(href):
            logger.info("entry_image_found", extra={
                "title": title,
                "link": link,
                "method": "article_page",
                "image_url": href,
            })
            return href

    logger.info("entry_image_missing", extra={
        "title": title,
        "link": link,
        "method": "none",
    })
    return None

def parse_feed(raw_xml: bytes, key_strategy: KeyStrategy | str = KeyStrategy.DEFAULT) -> List[ParsedItem]:
    if isinstance(key_strategy, str):
        try:
            key_strategy = KeyStrategy(key_strategy)
        except ValueError:
            key_strategy = KeyStrategy.DEFAULT

    parsed = feedparser.parse(raw_xml)

    logger.debug(
        "parse_feed start: bozo=%s entries=%d",
        getattr(parsed, "bozo", None),
        len(parsed.entries),
    )

    items: List[ParsedItem] = []
    seen_keys: Dict[str, Tuple[Optional[str], Optional[str]]] = {}

    for idx, entry in enumerate(parsed.entries):
        image_url = extract_image_url(entry, parsed)

        guid = entry.get("id") or entry.get("guid")
        link = entry.get("link")
        title = entry.get("title")
        summary = entry.get("summary") or entry.get("description")

        content_text: Optional[str] = None
        content = entry.get("content")
        if content and len(content) > 0:
            content_text = content[0].get("value") or summary
        else:
            content_text = summary

        published_struct = (
            entry.get("published_parsed")
            or entry.get("updated_parsed")
        )
        published_at = _to_datetime(published_struct)

        author = entry.get("author")

        entry_key = compute_entry_key(
            guid=guid,
            link=link,
            title=title,
            summary=summary,
            strategy=key_strategy,
        )

        prev = seen_keys.get(entry_key)
        if prev is not None:
            prev_title, prev_url = prev
            if (prev_title != title) or (prev_url != link):
                logger.warning(
                    "Suspicious entry_key collision: key=%s strategy=%s prev_title=%r prev_url=%r new_title=%r new_url=%r",
                    entry_key,
                    key_strategy.value,
                    prev_title,
                    prev_url,
                    title,
                    link,
                )
        else:
            seen_keys[entry_key] = (title, link)

        items.append(
            ParsedItem(
                entry_key=entry_key,
                url=link,
                title=title,
                author=author,
                summary=summary,
                content=content_text,
                published_at=published_at,
                image_url=image_url,
            )
        )
    logger.debug("parse_feed done: %d items parsed", len(items))
    return items