# -*- coding: utf-8 -*-
"""
하루 4회(10/12/15/18시 KST) 또는 수시 발송: 파트너사·임원인사 뉴스 수집 후 메일 본문 생성.
- 정기: 직전 발송 시각 이후 기사 / 수시(REQUEST_SCOPE=today): 당일 00:00~현재
- 트래킹: 임원인사 키워드 1개 이상 + 파트너사 키워드 1개 이상, 최근 한 달 이내 뉴스 기사만(블로그·논문 제외)
- 출력: [간결한 버전](첫 줄 제목은 '-' 없음, 이하 '-' bullet, 번호는 1. 2. 만) + [추가 내용]
- 인사 형태·이름 등은 기사 표현 그대로, 이름은 작은따옴표로 감쌈. 정보 부족 시 해당 bullet 생략 또는 '추가로 확인된 내용 없음'
※ 본문(전문) 분석은 원문 수집이 필요하며, 현재는 API 제목·요약만 사용합니다.
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

try:
    from article_body_fetcher import fetch_bodies_for_articles
except ImportError:
    def fetch_bodies_for_articles(articles, delay_sec=0.8):
        pass

KST = timezone(timedelta(hours=9))
MAIL_FROM = "wjdwndks99@gmail.com"
MAIL_TO = "juan.jung@navercorp.com"

# 검색·필터: 임원인사 관련 1개 이상 + 파트너사 관련 1개 이상 포함 기사만 트래킹
EXEC_KEYWORDS = [
    "임원인사", "선임", "내정", "영입", "임명", "연임", "역임", "복귀", "승진", "교체", "사임", "용퇴", "체제", "개편", "분사", "일원화",
]
PARTNER_KEYWORDS = [
    "삼성", "삼성전자", "신라면세점", "삼성SDS", "SK하이닉스", "SK", "SKT", "SK브로드밴드", "티맵모빌리티", "SK스퀘어", "SK플래닛",
    "현대", "현대차", "기아", "현대모비스", "현대카드", "42dot", "현대오토에버", "LG", "LG전자", "LG유플러스", "LG생활건강", "LG CNS", "HD현대중공업", "현대건설",
    "GS", "GS리테일", "GS칼텍스", "요기요", "GS건설", "호텔신라", "신세계", "이마트", "SSG닷컴", "스타벅스", "이베이",
    "롯데", "롯데쇼핑", "롯데렌탈", "카카오", "카카오모빌리티", "카카오페이", "카카오엔터", "CJ", "CJ ENM", "올리브영", "대한통운", "CGV", "대한항공", "아시아나", "한진칼",
    "BGF리테일", "BGF네트웍스", "LS", "LS전기", "KT", "쿠팡", "쿠팡플레이", "당근", "크래프톤", "휴맥스", "농심그룹", "한화", "한화에어로스페이스", "한화생명",
    "두나무", "업비트", "증권플러스비상장", "람다256", "두나무앤파트너스", "우아한형제들", "쏘카", "Meta", "메타", "Airbnb", "에어비앤비", "비바리퍼블리카",
    "Bytedance", "틱톡", "바이트댄스", "Uber", "우버", "Xsolla", "엑솔라", "다음", "DAUM", "업스테이지", "Adobe", "어도비", "Figma", "피그마", "Appning", "애프닝",
    "Netflix", "넷플릭스", "하이브", "넥슨", "Spotify", "스포티파이", "Disney", "디즈니", "메가박스", "LVMH", "CHANEL", "샤넬", "L'Oreal", "로레알",
    "인스파이어리조트", "이디야", "Huawei", "화웨이", "Novo Nordisk", "노보노디스크", "Harman", "하만", "Visa", "비자", "빗썸", "코인원", "코빗",
    "Google", "구글", "Microsoft", "마이크로소프트", "Amazon", "아마존", "OpenAI", "오픈AI", "Perplexity", "퍼플렉시티", "Anthropic", "앤스로픽", "Deepseek", "딥시크",
    "Apple", "애플", "Tesla", "테슬라", "Alibaba", "알리바바", "Walmart", "월마트", "Oracle", "오라클", "Palantir", "팔란티어", "Tencent", "텐센트",
]
# API 검색용 (임원인사 키워드로 검색)
KEYWORDS = EXEC_KEYWORDS
# 회사 추출용: 긴 이름 우선 매칭
COMPANY_PATTERNS = sorted(set(PARTNER_KEYWORDS), key=lambda x: -len(x))

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


# 인사/조직 키워드로 기사 유형 분류용
PERSON_KEYWORDS = ("선임", "영입", "내정", "임명", "사임", "교체", "용퇴", "승진", "연임", "대표", "CEO", "임원")
ORG_KEYWORDS = ("조직개편", "조직 개편", "신설", "팀", "본부", "분사", "일원화", "통합", "개편")


def _extract_company(title: str, description: str) -> str:
    """제목·요약에서 회사명 추출 (매칭되는 첫 번째)."""
    text = (title + " " + description).strip()
    for c in COMPANY_PATTERNS:
        if c in text:
            return c
    return "기사 참조"


def _extract_date_str(pub_date_str: str) -> str:
    """pubDate에서 yy/mm/dd 형식 문자열 반환."""
    dt = parse_pubdate(pub_date_str)
    if dt:
        return dt.strftime("%y/%m/%d")
    return "기사 참조"


def _extract_date_md(pub_date_str: str) -> str:
    """메신저용 날짜: M/D (예: 9/2)."""
    dt = parse_pubdate(pub_date_str)
    if dt:
        return f"{dt.month}/{dt.day}"
    return "기사 참조"


def _classify_article_type(title: str, description: str) -> str:
    """A=인사변동만, B=조직개편만, C=둘 다."""
    text = (title + " " + description).strip()
    has_person = any(k in text for k in PERSON_KEYWORDS)
    has_org = any(k in text for k in ORG_KEYWORDS)
    if has_person and has_org:
        return "C"
    if has_org:
        return "B"
    return "A"


def _pick_action_word(title: str, description: str, for_leave: bool = False) -> str:
    """기사에서 사용된 행동 단어 추출 (선임/영입/내정 또는 사임/교체/용퇴)."""
    text = (title + " " + description).strip()
    if for_leave:
        for w in ("사임", "교체", "용퇴"):
            if w in text:
                return w
        return "기사 참조"
    for w in ("선임", "영입", "내정", "임명"):
        if w in text:
            return w
    return "기사 참조"


def _build_concise_single(company: str, date_md: str, article: dict) -> list[str]:
    """단일 인사변동: [간결한 버전]. 본문 있으면 본문 기준으로 추출."""
    text = _article_text(article)
    title = (article.get("title") or "").strip()
    action = _pick_action_word(title, text, for_leave=False)
    action_leave = _pick_action_word(title, text, for_leave=True)
    lines = [f"{company} 인사변동 소식 공유드립니다. ({date_md})"]
    bullets = [
        f"- {company} [직무]에 '[이름]' {action} (상세: 기사 참조)",
        "- 경력: 기사 참조",
        "- [선임/영입/승진 배경 또는 이유] (기사 참조)",
        f"- [전임자] {action_leave} (기사 참조)",
    ]
    lines.extend(bullets[:5])
    return lines


def _build_concise_multi(company: str, date_md: str, clusters: list[list[dict]]) -> list[str]:
    """여러 명/여러 조직: 1. 2. 번호 묶음, 각 그룹당 최대 5개 bullet."""
    lines = [f"{company} 인사변동 소식 공유드립니다. ({date_md})"]
    for i, cl in enumerate(clusters, 1):
        rep = max(cl, key=lambda a: len(_article_text(a)))
        title = (rep.get("title") or "").strip()
        text = _article_text(rep)
        action = _pick_action_word(title, text, for_leave=False)
        action_leave = _pick_action_word(title, text, for_leave=True)
        lines.append(f"{i}. [계열사/사업부] (기사 참조)")
        bullets = [
            f"- {company} [직무]에 '[이름]' {action} (기사 참조)",
            "- 경력: 기사 참조",
            "- [배경 또는 이유] (기사 참조)",
            f"- [전임자 관련 변화] (기사 참조)",
        ]
        for b in bullets[:5]:
            lines.append(b)
    return lines


def _article_text(a: dict) -> str:
    """본문이 있으면 본문, 없으면 요약. 요약·본문 기반 추출에 사용."""
    body = (a.get("body") or "").strip()
    if body:
        return body
    return (a.get("title") or "").strip() + " " + (a.get("description") or "").strip()


def _build_extra_block(articles: list[dict]) -> list[str]:
    """[추가 내용]: 보완 정보만 '-' bullet. 본문이 있으면 본문 일부 활용."""
    lines = []
    seen = set()
    for a in articles[:3]:
        text = _article_text(a)
        snippet = (text or "").strip()[:300].replace("\n", " ")
        if not snippet:
            continue
        if snippet in seen:
            continue
        seen.add(snippet)
        date_md = _extract_date_md(a.get("pubDate", ""))
        lines.append(f"- {snippet}… (기사 참조, {date_md})")
    if not lines:
        lines.append("- 추가로 확인된 내용 없음")
    return lines[:5]


def build_template_bullets(article: dict) -> list[str]:
    """(레거시) 형식 A/B/C 하위 bullet. 신규 출력은 _build_concise_* 사용."""
    title = (article.get("title") or "").strip()
    text = _article_text(article)
    pub = article.get("pubDate", "")
    company = _extract_company(title, text)
    date_str = _extract_date_str(pub)
    atype = _classify_article_type(title, text)
    action = _pick_action_word(title, text, for_leave=False)
    action_leave = _pick_action_word(title, text, for_leave=True)
    if atype == "A":
        return [
            f"{company} 임원인사 내용 공유 ({date_str} 발표)",
            f"- {company} [직무]에 '[이름]' {action} (기사 참조)",
            "- 경력: 기사 참조",
            f"- [전임자] {action_leave} (기사 참조)",
        ]
    if atype == "B":
        return [
            f"{company} 조직개편 내용 공유 ({date_str} 발표)",
            "- [신설/개편 내용] (기사 참조)",
        ]
    return [
        f"{company} 임원인사 및 조직개편 내용 공유 ({date_str} 발표)",
        "- (기사 참조)",
    ]


def _title_normalize(s: str) -> str:
    """동일 뉴스 판별용 제목 정규화."""
    s = re.sub(r"[^\w\s가-힣a-zA-Z0-9]", " ", s or "")
    return " ".join((s or "").split()).strip()


def _is_same_news(a1: dict, a2: dict) -> bool:
    """동일 회사·동일 이벤트로 보이는지 (제목 유사도)."""
    t1 = _title_normalize(a1.get("title", ""))
    t2 = _title_normalize(a2.get("title", ""))
    if not t1 or not t2:
        return False
    w1, w2 = set(t1.split()), set(t2.split())
    if not w1 or not w2:
        return False
    overlap = len(w1 & w2) / max(len(w1), len(w2))
    return overlap >= 0.5 or (t1 in t2 or t2 in t1)


def _group_by_company(articles: list[dict]) -> dict[str, list[dict]]:
    """회사별로 기사 묶음. '기사 참조'는 회사 미상이므로 문단 합치지 않음."""
    groups: dict[str, list[dict]] = {}
    for a in articles:
        company = _extract_company(a.get("title", ""), a.get("description", ""))
        if company == "기사 참조":
            key = f"_unk_{len(groups)}"
        else:
            key = company
        if key not in groups:
            groups[key] = []
        groups[key].append(a)
    return groups


def _pick_best_link(articles: list[dict]) -> tuple[str, list[dict]]:
    """동일 뉴스 복수 출처 시 정보가 가장 많은(description 가장 긴) 기사 링크 선택. 반환: (link, 동일 뉴스로 묶인 기사 목록)."""
    if not articles:
        return "", []
    if len(articles) == 1:
        return (articles[0].get("link") or "").strip(), articles
    best = max(articles, key=lambda a: len((a.get("description") or "")))
    return (best.get("link") or "").strip(), articles


def _cluster_same_news(company_articles: list[dict]) -> list[list[dict]]:
    """한 회사 내에서 동일 뉴스(여러 출처)끼리 묶음. 서로 다른 이벤트는 별도 클러스터."""
    if not company_articles:
        return []
    clusters: list[list[dict]] = []
    for a in company_articles:
        placed = False
        for cl in clusters:
            if _is_same_news(a, cl[0]):
                cl.append(a)
                placed = True
                break
        if not placed:
            clusters.append([a])
    return clusters


def _merge_one_company(company: str, company_articles: list[dict]) -> tuple[str, str, list[str], list[str]]:
    """한 회사 문단: 제목줄, 대표 링크, [간결한 버전] 라인 목록, [추가 내용] 라인 목록."""
    if company.startswith("_unk_"):
        a = company_articles[0]
        title = (a.get("title") or "").strip()
        link = (a.get("link") or "").strip()
        date_md = _extract_date_md(a.get("pubDate", ""))
        concise = [f"[회사 미상] 인사변동 소식 공유드립니다. ({date_md})"]
        concise.append(f"- {title} (기사 참조)")
        extra = _build_extra_block(company_articles)
        return title, link, concise, extra
    clusters = _cluster_same_news(company_articles)
    best_article = max(company_articles, key=lambda a: len((a.get("description") or "")))
    best_link = (best_article.get("link") or "").strip()
    date_md = _extract_date_md(best_article.get("pubDate", ""))
    if len(clusters) <= 1:
        rep = clusters[0][0] if clusters else best_article
        concise = _build_concise_single(company, date_md, rep)
    else:
        concise = _build_concise_multi(company, date_md, clusters)
    extra = _build_extra_block(company_articles)
    one_line = concise[0] if concise else f"{company} 인사·조직 관련"
    return one_line, best_link, concise, extra


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
                now = now_kst()
                if pub_dt < now - timedelta(days=30):
                    continue
                link_lower = link.lower()
                if "blog." in link_lower or "cafe." in link_lower or "kin." in link_lower:
                    continue
                title_clean = strip_html(item.get("title", ""))
                desc_clean = strip_html(item.get("description", ""))
                text = (title_clean + " " + desc_clean).strip()
                if not any(k in text for k in EXEC_KEYWORDS):
                    continue
                if not any(k in text for k in PARTNER_KEYWORDS):
                    continue
                seen_links.add(link)
                articles.append({
                    "title": title_clean,
                    "link": link,
                    "description": desc_clean,
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
    """회사별 [간결한 버전] + [추가 내용], 메신저 공유 최적화. 첫 줄은 '-' 없음, 이하 '-' bullet, 번호는 1. 2. 만 사용."""
    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>",
        "<p>임원인사·파트너사 관련 뉴스 (최근 한 달 이내 뉴스 기사 기준)</p>",
        "<ul>",
    ]
    groups = _group_by_company(articles)
    for key, company_articles in sorted(groups.items(), key=lambda x: (x[0].startswith("_unk_"), x[0])):
        if not company_articles:
            continue
        title_line, link, concise, extra = _merge_one_company(key, company_articles)
        if not title_line:
            continue
        link_html = f' <a href="{link}">기사 보기</a>' if link else ""
        lines.append(f"  <li><strong>{title_line}</strong>{link_html}")
        lines.append("    <p><strong>[간결한 버전]</strong></p>")
        lines.append("    <ul>")
        for i, line in enumerate(concise):
            if not line or not line.strip():
                continue
            if i == 0:
                lines.append(f"      <li>{line.strip()}</li>")
            elif line.strip().startswith("-"):
                lines.append(f"      <li>{line.strip()}</li>")
            elif re.match(r"^\d+\.", line.strip()):
                lines.append(f"      <li><strong>{line.strip()}</strong></li>")
            else:
                lines.append(f"      <li>- {line.strip()}</li>")
        lines.append("    </ul>")
        lines.append("    <p><strong>[추가 내용]</strong></p>")
        lines.append("    <ul>")
        for line in extra:
            if line and line.strip():
                lines.append(f"      <li>{line.strip()}</li>")
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
    fetch_bodies_for_articles(articles)
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
