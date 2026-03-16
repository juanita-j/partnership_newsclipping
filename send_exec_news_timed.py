# -*- coding: utf-8 -*-
"""
하루 4회(10/12/15/18시 KST) 또는 수시 발송용: 기사 수집 후 메일 본문 생성.
- 정기(스케줄): 직전 발송 시각 이후 기사 (10시→전날18시, 12시→10시, 15시→12시, 18시→15시)
- 수시(workflow_dispatch): 당일 00:00 KST ~ 요청 시각까지 기사 (env REQUEST_SCOPE=today)
제목: 인사변동 업데이트 (yy/mm/dd)
본문: 상위 bullet = 한줄 요약 + 링크, 하위 bullet = 주요 내용 3~5개
"""
import os
import re
import json
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

try:
    import requests
except ImportError:
    print("pip install requests 후 다시 실행해 주세요.")
    raise

KST = timezone(timedelta(hours=9))
MAIL_FROM = "wjdwndks99@gmail.com"
MAIL_TO = "juan.jung@navercorp.com"
KEYWORDS = ["임원인사", "선임", "내정", "교체", "영입", "사임", "용퇴", "체제", "개편", "인사변동"]
MAX_ARTICLES = 50
NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"
OUTPUT_DIR = Path(__file__).resolve().parent
EMAIL_JSON = OUTPUT_DIR / "email_content.json"

# 발송 시각 (KST)
RUN_HOURS_KST = (10, 12, 15, 18)


def now_kst() -> datetime:
    return datetime.now(KST)


def get_since_datetime(now: datetime, since_today_midnight: bool = False) -> datetime:
    """'직전 업데이트' 시각 반환.
    since_today_midnight=True(수시 발송): 당일 00:00 KST
    False(정기 발송): 10시→전날18시, 12시→당일10시, 15시→당일12시, 18시→당일15시
    """
    if since_today_midnight:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    h = now.hour
    if h < 12:
        since = (now - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    elif h < 15:
        since = now.replace(hour=10, minute=0, second=0, microsecond=0)
    elif h < 18:
        since = now.replace(hour=12, minute=0, second=0, microsecond=0)
    else:
        since = now.replace(hour=15, minute=0, second=0, microsecond=0)
    return since


def parse_pubdate(s: str) -> datetime | None:
    """네이버 API pubDate 문자열을 KST datetime으로 변환."""
    if not s or not s.strip():
        return None
    try:
        dt = parsedate_to_datetime(s.strip())
        return dt.astimezone(KST)
    except Exception:
        return None


def strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def fetch_news(client_id: str, client_secret: str, query: str, display: int = 20, start: int = 1):
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    params = {"query": query, "display": min(display, 100), "start": start, "sort": "date"}
    r = requests.get(NEWS_API_URL, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def description_to_points(desc: str, max_points: int = 5) -> list[str]:
    """요약문을 문장 단위로 나누어 최대 max_points개 하위 bullet으로."""
    if not desc or not desc.strip():
        return []
    text = strip_html(desc).strip()
    # 문장 구분: . ! ? 후 공백 또는 줄끝
    parts = re.split(r"(?<=[.!?])\s+", text)
    points = [p.strip() for p in parts if p.strip()][:max_points]
    if not points and text:
        # 한 문장도 없으면 길이로 자르기
        chunk = 80
        points = [text[i : i + chunk].strip() for i in range(0, min(len(text), chunk * max_points), chunk) if text[i : i + chunk].strip()]
    return points[:max_points]


def collect_articles_since(client_id: str, client_secret: str, since_dt: datetime) -> list[dict]:
    seen_links = set()
    articles = []

    for keyword in KEYWORDS:
        if len(articles) >= MAX_ARTICLES:
            break
        try:
            data = fetch_news(client_id, client_secret, keyword, display=30)
            for item in data.get("items", []):
                link = item.get("link") or item.get("originallink") or ""
                if not link or link in seen_links:
                    continue
                pub_dt = parse_pubdate(item.get("pubDate", ""))
                if pub_dt is None or pub_dt <= since_dt:
                    continue
                seen_links.add(link)
                articles.append({
                    "title": strip_html(item.get("title", "")),
                    "link": link,
                    "description": strip_html(item.get("description", "")),
                    "pubDate": item.get("pubDate", ""),
                })
                if len(articles) >= MAX_ARTICLES:
                    break
        except Exception as e:
            print(f"키워드 '{keyword}' 검색 오류: {e}")
            continue

    # pubDate 기준 최신순 유지 (API가 date sort라 대체로 이미 정렬됨)
    return articles[:MAX_ARTICLES]


def build_subject(now: datetime) -> str:
    return f"인사변동 업데이트 ({now.strftime('%y/%m/%d')})"


def build_body_html(articles: list) -> str:
    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>",
        "<p>임원인사·선임·내정·교체·영입·사임·용퇴·체제·개편 관련 뉴스 (직전 업데이트 이후)</p>",
        "<ul>",
    ]
    for a in articles:
        title = (a.get("title") or "").strip()
        link = (a.get("link") or "").strip()
        points = description_to_points(a.get("description", ""), max_points=5)
        if not title:
            continue
        link_html = f' <a href="{link}">기사 보기</a>' if link else ""
        lines.append(f"  <li><strong>{title}</strong>{link_html}")
        if points:
            lines.append("    <ul>")
            for p in points:
                if p:
                    lines.append(f"      <li>{p}</li>")
            lines.append("    </ul>")
        lines.append("  </li>")
    lines.append("</ul></body></html>")
    return "\n".join(lines)


def main() -> int:
    client_id = os.environ.get("NAVER_CLIENT_ID", "").strip()
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("환경 변수 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 을 설정해 주세요.")
        return 1

    now = now_kst()
    # 수시 발송(REQUEST_SCOPE=today): 당일 00:00~현재. 정기: 직전 발송 시각 이후
    since_today = os.environ.get("REQUEST_SCOPE", "").strip().lower() == "today"
    since = get_since_datetime(now, since_today_midnight=since_today)
    print(f"실행 시각(KST): {now}")
    print(f"구간: {'당일 00:00 ~' if since_today else '직전 발송 ~'} 이후 기사 수집")
    print(f"since = {since}")

    articles = collect_articles_since(client_id, client_secret, since)
    subject = build_subject(now)
    body_html = build_body_html(articles)

    payload = {
        "to": MAIL_TO,
        "subject": subject,
        "body": body_html,
        "contentType": "html",
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(EMAIL_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"제목: {subject}")
    print(f"수신: {MAIL_TO}")
    print(f"기사 수: {len(articles)}건")
    print(f"저장: {EMAIL_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
