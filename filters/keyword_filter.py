"""
주요 뉴스 키워드 필터: config/keywords.yaml 기준 1개 이상 포함 시 통과.
블로그 URL 제외, URL 기준 중복 제거.
제목에 파트너사명 미포함·코스피/코스닥/소액주주·특집/인사이트 리포트 등 관련도 낮은 기사 제외.
"""
from pathlib import Path

from collectors.base import Article

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
KEYWORDS_FILE = CONFIG_DIR / "keywords.yaml"
PARTNERS_FILE = CONFIG_DIR / "partners.yaml"

# 관련도 낮아 제외할 키워드 (제목 또는 본문에 포함 시 제외)
EXCLUDE_KEYWORDS = [
    "코스피",
    "코스닥",
    "소액주주",
    "인사이트 리포트",
    "특집기사",
    "특집 시리즈",
    "노동조합",
    "노조",
]


def load_keywords() -> list[str]:
    """keywords.yaml에서 그룹별 키워드를 평탄화하여 반환."""
    try:
        import yaml
    except ImportError:
        return _fallback_keywords()
    if not KEYWORDS_FILE.exists():
        return _fallback_keywords()
    with open(KEYWORDS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    groups = data.get("groups") or {}
    keywords: list[str] = []
    for g in groups.values():
        keywords.extend(g)
    return list(dict.fromkeys(keywords))


def _fallback_keywords() -> list[str]:
    """yaml 없을 때 하드코딩 키워드."""
    return [
        "신사업", "신제품", "출시", "공개", "오픈", "확대", "확장", "진출", "기능", "도입", "시작", "추가",
        "개발", "테스트", "고도화", "강화", "체계화", "보완", "개선", "업데이트", "출범", "변경", "론칭", "런칭",
        "추진", "개편", "건립", "설립", "참전", "착수",
        "제휴", "협력", "협약", "업무협약", "파트너십", "파트너사", "MOU", "체결", "연동", "연계", "제공",
        "확보", "지원", "수출", "참여", "컨소시엄", "컨소시움", "맞손", "손잡고", "협상",
        "투자", "인수", "흡수", "합병", "매각", "주가", "실적", "분사", "재무", "계열사 정리", "구매",
        "지분", "지분교환", "상장", "기업공개", "IPO", "검토",
        "종료", "중단", "축소", "폐쇄", "폐지", "퇴출", "과징금", "규제", "고발", "항소", "피해", "공정위", "조사",
    ]


# 블로그 URL 제외
BLOG_PATTERNS = ("blog.", "블로그", "tistory", "brunch")


def is_blog_url(url: str) -> bool:
    return any(p in url.lower() for p in BLOG_PATTERNS)


def load_partner_names() -> dict[str, list[str]]:
    """partner_id -> 해당 파트너사 이름 리스트 (제목에 파트너사명 포함 여부 검사용)."""
    try:
        import yaml
        if not PARTNERS_FILE.exists():
            return {}
        with open(PARTNERS_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        partners = data.get("partners") or []
        return {p["id"]: (p.get("names") or [p["id"]]) for p in partners if p.get("id")}
    except Exception:
        return {}


def _title_contains_partner(article: Article, partner_names: dict[str, list[str]]) -> bool:
    """제목에 해당 파트너사명이 1개 이상 들어가 있으면 True."""
    names = partner_names.get(article.partner_id) or []
    if not names:
        return True
    title = article.title or ""
    return any(name in title for name in names)


def _contains_exclude_keywords(text: str) -> bool:
    """제외 키워드(코스피/코스닥/소액주주/특집기사 등)가 포함되면 True."""
    t = text or ""
    for kw in EXCLUDE_KEYWORDS:
        if kw in t:
            return True
    return False


def filter_articles(articles: list[Article], keywords: list[str] | None = None) -> list[Article]:
    """
    키워드 1개 이상 포함 + 블로그 제외 + URL 중복 제거.
    + 제목에 파트너사명 미포함 제외, 코스피/코스닥/소액주주/특집기사 등 제외 키워드 포함 시 제외.
    """
    if keywords is None:
        keywords = load_keywords()
    partner_names = load_partner_names()
    seen_urls: set[str] = set()
    result: list[Article] = []
    text_lower = {k: k.lower() for k in keywords}
    keyword_set = set(text_lower.values())

    for a in articles:
        if is_blog_url(a.url):
            continue
        norm_url = a.url.strip().rstrip("/")
        if norm_url in seen_urls:
            continue
        combined = (a.title + " " + a.body).lower()
        if not any(k in combined for k in keyword_set):
            continue
        if not _title_contains_partner(a, partner_names):
            continue
        if _contains_exclude_keywords((a.title or "") + " " + (a.body or "")):
            continue
        seen_urls.add(norm_url)
        result.append(a)
    return result
