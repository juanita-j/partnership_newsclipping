"""
Google News RSS/수집 (보조 소스).
feedparser로 Google News RSS 피드 수집.
"""
from datetime import datetime, timezone, timedelta
import re

from .base import Article, BaseCollector

try:
    import feedparser
except ImportError:
    feedparser = None

# 블로그 등 제외할 출처 키워드 (선택)
BLOG_KEYWORDS = re.compile(r"blog|블로그", re.I)


class GoogleNewsCollector(BaseCollector):
    """Google News RSS 수집기."""

    # Google News RSS (검색어 치환)
    RSS_URL = "https://news.google.com/rss/search?q={query}+when:7d&hl=ko&gl=KR&ceid=KR:ko"

    def collect(
        self,
        query: str,
        partner_id: str,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Article]:
        if not feedparser:
            return []
        from urllib.parse import quote_plus
        url = self.RSS_URL.format(query=quote_plus(query))
        try:
            feed = feedparser.parse(url)
        except Exception:
            return []

        articles: list[Article] = []
        for e in feed.entries[:limit]:
            link = e.get("link") or e.get("id") or ""
            title = (e.get("title") or "").strip()
            summary = e.get("summary", "") or ""
            summary = re.sub(r"<[^>]+>", "", summary).strip()
            published = e.get("published_parsed")
            if published:
                pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                if since:
                    since_utc = since.astimezone(timezone.utc) if since.tzinfo else since.replace(tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)
                    if pub_dt < since_utc:
                        continue
            else:
                pub_dt = None
            source = (e.get("source", {}) or {}).get("title", "Google News")
            if BLOG_KEYWORDS.search(source):
                continue
            body = summary or title
            articles.append(
                Article(
                    title=title,
                    url=link,
                    source=source,
                    published_at=pub_dt,
                    body=body,
                    partner_id=partner_id,
                    raw=dict(e),
                )
            )
        return articles
