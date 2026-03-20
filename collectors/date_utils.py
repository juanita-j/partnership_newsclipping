"""
기사 발행일 표시용: published_at 보강 및 mm/dd 포맷.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

from collectors.base import Article

KST = timezone(timedelta(hours=9))


def resolve_article_published_at(article: Article) -> datetime | None:
    """Article.published_at 또는 raw(pubDate, published_parsed 등)에서 시각 복원."""
    dt = getattr(article, "published_at", None)
    if dt is not None:
        try:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=KST)
            return dt
        except Exception:
            pass

    raw = getattr(article, "raw", None) or {}
    if not isinstance(raw, dict):
        return None

    pub = raw.get("pubDate")
    if isinstance(pub, str) and pub.strip():
        try:
            return parsedate_to_datetime(pub.strip())
        except (TypeError, ValueError):
            pass

    pp = raw.get("published_parsed")
    if pp is not None:
        try:
            t = pp[:6]
            return datetime(*t, tzinfo=timezone.utc)
        except Exception:
            pass

    pub2 = raw.get("published")
    if isinstance(pub2, str) and pub2.strip():
        try:
            return parsedate_to_datetime(pub2.strip())
        except (TypeError, ValueError):
            pass

    return None


def format_article_mmdd(article: Article, fallback: datetime | None = None) -> str:
    """항상 mm/dd 문자열. 알 수 없으면 fallback(없으면 현재 KST)."""
    dt = resolve_article_published_at(article)
    if dt is None:
        dt = fallback or datetime.now(KST)
    try:
        if dt.tzinfo:
            dt = dt.astimezone(KST)
        else:
            dt = dt.replace(tzinfo=KST)
        return dt.strftime("%m/%d")
    except Exception:
        return (fallback or datetime.now(KST)).strftime("%m/%d")
