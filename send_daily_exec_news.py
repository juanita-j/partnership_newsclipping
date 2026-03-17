# -*- coding: utf-8 -*-
"""
매일 오전 10시 실행: 임원인사 관련 뉴스 10건 수집 후 메일 본문 생성/발송.
- 수신: juan.jung@navercorp.com
- 제목: x월 xx일 오전 10시 임원인사 현황
- 키워드: 인사변동, 임원인사, 내정, 선임, 교체
"""
import os
import re
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# 선택: .env 파일에서 환경 변수 로드 (pip install python-dotenv)
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

# 설정
MAIL_TO = "juan.jung@navercorp.com"
KEYWORDS = ["인사변동", "임원인사", "내정", "선임", "교체"]
MAX_ARTICLES = 10
NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"
OUTPUT_DIR = Path(__file__).resolve().parent
EMAIL_JSON = OUTPUT_DIR / "email_content.json"


def strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def fetch_news(client_id: str, client_secret: str, query: str, display: int = 10, start: int = 1):
    """네이버 뉴스 검색 API 호출"""
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {"query": query, "display": min(display, 100), "start": start, "sort": "date"}
    r = requests.get(NEWS_API_URL, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def collect_articles(client_id: str, client_secret: str) -> list:
    """여러 키워드로 검색해 중복 제거 후 최대 10건 수집"""
    seen_links = set()
    articles = []

    for keyword in KEYWORDS:
        if len(articles) >= MAX_ARTICLES:
            break
        try:
            data = fetch_news(client_id, client_secret, keyword, display=5)
            for item in data.get("items", []):
                link = item.get("link") or item.get("originallink") or ""
                if link and link not in seen_links:
                    seen_links.add(link)
                    articles.append({
                        "title": strip_html(item.get("title", "")),
                        "link": link,
                        "originallink": item.get("originallink", ""),
                        "description": strip_html(item.get("description", "")),
                        "pubDate": item.get("pubDate", ""),
                    })
                    if len(articles) >= MAX_ARTICLES:
                        break
        except Exception as e:
            print(f"키워드 '{keyword}' 검색 오류: {e}")
            continue

    return articles[:MAX_ARTICLES]


def build_subject() -> str:
    now = datetime.now()
    return f"{now.month}월 {now.day}일 오전 10시 임원인사 현황"


def build_body_html(articles: list) -> str:
    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>",
        "<h2>임원인사 관련 뉴스 (인사변동 / 임원인사 / 내정 / 선임 / 교체)</h2>",
        "<ul>",
    ]
    for i, a in enumerate(articles, 1):
        title = a.get("title", "")
        link = a.get("link", "")
        desc = (a.get("description", "") or "")[:200]
        if desc:
            desc = desc + "…" if len(a.get("description", "")) > 200 else desc
        lines.append(
            f"<li><strong>{i}. <a href='{link}'>{title}</a></strong><br/>"
            f"<small>{desc}</small></li>"
        )
    lines.append("</ul></body></html>")
    return "\n".join(lines)


def main():
    client_id = os.environ.get("NAVER_CLIENT_ID", "").strip()
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("환경 변수 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 을 설정해 주세요.")
        print("네이버 개발자 센터(https://developers.naver.com)에서 검색 API 앱 등록 후 발급받을 수 있습니다.")
        return 1

    articles = collect_articles(client_id, client_secret)
    if not articles:
        print("수집된 뉴스가 없습니다.")
        articles = []

    subject = build_subject()
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
    print(f"내용 저장: {EMAIL_JSON}")

    # 선택: SMTP로 직접 발송 (SMTP_* 환경 변수 설정 시)
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()
    if smtp_host and smtp_user and smtp_password:
        if send_via_smtp(subject, body_html, smtp_host, smtp_user, smtp_password):
            print("SMTP로 메일 발송 완료.")
        else:
            print("SMTP 발송 실패. Cursor에서 mail_send 로 보낼 수 있습니다.")
    else:
        print("\nCursor에서 naver-works MCP의 mail_send 로 위 내용을 보내려면:")
        print("  '오늘자 임원인사 뉴스 메일 보내줘' 라고 요청하세요.")
    return 0


def send_via_smtp(subject: str, body_html: str, host: str, user: str, password: str) -> bool:
    """SMTP로 메일 발송 (회사 SMTP 사용 시)"""
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        port = 587
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = MAIL_TO
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    try:
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            s.login(user, password)
            s.sendmail(user, [MAIL_TO], msg.as_string())
        return True
    except Exception as e:
        print(f"SMTP 오류: {e}")
        return False


if __name__ == "__main__":
    exit(main())
