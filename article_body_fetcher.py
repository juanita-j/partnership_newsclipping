# -*- coding: utf-8 -*-
"""
뉴스 기사 URL → 본문 전문 추출.

[조사 결과]
- 네이버 검색 API: 본문 미제공. 제목·링크·요약·날짜만 제공.
- 본문 확보 방법:
  1) 직접 크롤링: requests + BeautifulSoup, 네이버/언론사별 셀렉터 사용.
  2) URL→텍스트 API: Jina Reader (https://r.jina.ai/URL) 무료 사용 가능, 별도 키 없이 호출 가능.

동작: 먼저 직접 크롤링(네이버·일반 셀렉터) 시도 → 실패 또는 빈 본문이면 Jina Reader fallback.
환경 변수 FETCH_ARTICLE_BODY=1 일 때만 본문 수집 수행. USE_JINA_READER=1 이면 크롤링 건너뛰고 Jina만 사용.
"""
import os
import re
import time

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# 기본 User-Agent (봇 차단 완화)
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}
REQUEST_TIMEOUT = 15
JINA_TIMEOUT = 25
DELAY_SEC = 0.8

# 네이버·언론사별 본문 셀렉터 (우선순위)
BODY_SELECTORS = [
    "#articleBodyContents",  # 네이버 일반 뉴스
    "#newsct_article",
    "#dic_area",
    "#articeBody",   # 연예 (오타 원문 유지)
    "#newsEndContents",  # 스포츠
    "article .news_body",
    "article .article_body",
    ".article_body",
    ".news_body",
    "[itemprop='articleBody']",
    "article",
]


def _clean_body(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text.strip()


def _fetch_html(url: str) -> tuple[str | None, str]:
    """URL GET 후 (최종 URL, HTML 텍스트) 반환. 실패 시 (None, '')."""
    if not requests:
        return None, ""
    try:
        r = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        r.raise_for_status()
        return r.url, (r.text or "")
    except Exception:
        return None, ""


def _extract_by_selectors(soup, selectors: list[str]) -> str:
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return _clean_body(el.get_text(separator=" ", strip=True))
    return ""


def fetch_by_crawl(url: str) -> str:
    """직접 크롤링으로 본문 추출. 네이버·일반 셀렉터 지원."""
    if not BeautifulSoup or not requests:
        return ""
    final_url, html = _fetch_html(url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    body = _extract_by_selectors(soup, BODY_SELECTORS)
    if body and len(body) > 100:
        return body
    return ""


def fetch_by_jina(url: str) -> str:
    """Jina Reader API: https://r.jina.ai/{url} → 마크다운/텍스트. API 키 없이 호출 가능."""
    if not requests:
        return ""
    jina_url = "https://r.jina.ai/" + url
    try:
        r = requests.get(
            jina_url,
            headers={**DEFAULT_HEADERS, "X-Return-Format": "markdown"},
            timeout=JINA_TIMEOUT,
        )
        r.raise_for_status()
        text = (r.text or "").strip()
        return _clean_body(text) if len(text) > 100 else ""
    except Exception:
        return ""


def fetch_article_body(url: str, use_jina_first: bool = False) -> str:
    """
    기사 URL에서 본문 전문 추출.
    use_jina_first=True 이면 크롤링 건너뛰고 Jina Reader만 사용.
    """
    if not url or not url.strip():
        return ""
    url = url.strip()
    if use_jina_first:
        body = fetch_by_jina(url)
        if body:
            return body
        return fetch_by_crawl(url)
    body = fetch_by_crawl(url)
    if body:
        return body
    return fetch_by_jina(url)


def fetch_bodies_for_articles(articles: list[dict], delay_sec: float = DELAY_SEC) -> None:
    """articles 리스트를 in-place로 수정: 각 항목에 'body' 키로 본문 추가. FETCH_ARTICLE_BODY=1 일 때만 수행."""
    if os.environ.get("FETCH_ARTICLE_BODY", "").strip() != "1":
        return
    use_jina_first = os.environ.get("USE_JINA_READER", "").strip() == "1"
    for i, a in enumerate(articles):
        link = (a.get("link") or "").strip()
        if not link:
            continue
        a["body"] = fetch_article_body(link, use_jina_first=use_jina_first)
        if delay_sec and i < len(articles) - 1:
            time.sleep(delay_sec)
