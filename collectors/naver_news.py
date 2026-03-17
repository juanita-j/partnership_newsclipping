"""
네이버 뉴스 검색 API를 이용한 수집기.
https://developers.naver.com/docs/serviceapi/search/news/news.md
"""
from datetime import datetime, timezone, timedelta
from html import unescape
import os
import re
import time

from .base import Article, BaseCollector

try:
    import requests
except ImportError:
    requests = None


NAVER_NEWS_API = "https://openapi.naver.com/v1/search/news.json"
# 블로그 URL 패턴 제외용
NAVER_BLOG_PATTERN = re.compile(r"blog\.naver\.com|blog\.me", re.I)


class NaverNewsCollector(BaseCollector):
    """네이버 뉴스 검색 API 수집기."""

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self.client_id = client_id or os.environ.get("NAVER_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("NAVER_CLIENT_SECRET", "")

    def collect(
        self,
        query: str,
        partner_id: str,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Article]:
        if not requests:
            raise RuntimeError("requests 패키지가 필요합니다: pip install requests")
        if not self.client_id or not self.client_secret:
            return []

        all_items: list[Article] = []
        start = 1
        display = min(100, limit)

        while start <= limit:
            params = {
                "query": query,
                "display": display,
                "start": start,
                "sort": "date",
            }
            headers = {
                "X-Naver-Client-Id": self.client_id,
                "X-Naver-Client-Secret": self.client_secret,
            }
            try:
                resp = requests.get(NAVER_NEWS_API, params=params, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                break

            items = data.get("items") or []
            if not items:
                break

            for it in items:
                link = it.get("link") or it.get("originallink") or ""
                if NAVER_BLOG_PATTERN.search(link):
                    continue
                title = _strip_tag(it.get("title") or "")
                description = _strip_tag(it.get("description") or "")
                pub_date_str = it.get("pubDate") or ""
                pub_dt = _parse_naver_date(pub_date_str) if pub_date_str else None
                if pub_dt and not pub_dt.tzinfo:
                    pub_dt = pub_dt.replace(tzinfo=timezone(timedelta(hours=9)))
                if since and pub_dt and pub_dt < since:
                    continue
                all_items.append(
                    Article(
                        title=title,
                        url=link,
                        source="네이버 뉴스",
                        published_at=pub_dt,
                        body=description,
                        partner_id=partner_id,
                        raw=dict(it),
                    )
                )

            if len(items) < display:
                break
            start += display
            time.sleep(0.1)

        return all_items


def _strip_tag(s: str) -> str:
    s = unescape(s)
    return re.sub(r"<[^>]+>", "", s).strip()


def _parse_naver_date(s: str) -> datetime | None:
    """RFC 2822 형식 등 파싱 시도."""
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(s.strip()[:30], fmt.replace(" %z", "").replace(" %Z", ""))
        except ValueError:
            continue
    return None
