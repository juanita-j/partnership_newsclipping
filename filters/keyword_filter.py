"""
주요 뉴스 키워드 필터: config/keywords.yaml 기준 1개 이상 포함 시 통과.
블로그 URL 제외, URL 기준 중복 제거.
제목에 파트너사명 미포함·코스피/코스닥·공시/배당/주가·특집/리포트 등
(신제품·전략·재무·사업 리스크 중심이 아닌) 관련도 낮은 기사·채용/공채/신입 뉴스 제외.
"""
from __future__ import annotations

import re
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
    # 스포츠 선수 관련 (야구·농구·배구·축구 등)
    "야구",
    "농구",
    "배구",
    "축구",
    "스포츠",
    "투수",
    "타자",
    "외야수",
    "내야수",
    "포수",
    # 이벤트/특가 관련
    "이벤트",
    "화이트데이",
    "특가",
    # 임원진 탐구 관련 특집기사
    "임원진 탐구",
    "C-레벨 탐구",
    "C레벨 탐구",
    "Who?",
    # 보고서·주가 변동 위주 기사 제외
    "보고서 발표",
    "주식 가격 상승",
    "주식 가격 하락",
    "주식 가격 변동",
    "주가 상승",
    "주가 하락",
    "주가 변동",
    "주가 급락",
    "주가 급등",
    "주가 상승 이유",
    "특징주",
    # 공시·배당·산학·조사·리포트·콘텐츠 비본업 뉴스
    "공시",
    "배당",
    "산학협력",
    "설문조사",
    "트렌드 리포트",
    "카피라이터",
    # 채용·공채 관련
    "채용",
    "공채",
    "신입",
]

# 제목·본문에서 단어 경계로만 인정할 파트너 id (현재: 메타 — '메타비아'·'메타세쿼이아' 등 제외)
_STANDALONE_KO_META_PARTNERS = frozenset({"meta"})

# 한글/영숫자 등 — 띄어쓰기 없이 붙으면 동일 단어로 보지 않음
_BOUNDARY_OK = frozenset(
    " \t\n\r,.;:!?'\"()[]{}「」【】·<>《》〈〉…／/\\-•|&@#%^*+=~`"
)


def _is_word_gluing_char(c: str) -> bool:
    """True면 앞뒤 글자와 같은 '단어'로 붙은 것으로 간주."""
    if not c:
        return False
    if c.isspace() or c in _BOUNDARY_OK:
        return False
    o = ord(c)
    if 0xAC00 <= o <= 0xD7A3:  # 한글 음절
        return True
    if c.isascii() and (c.isalnum() or c == "_"):
        return True
    return False


def _has_standalone_substring(text: str, needle: str) -> bool:
    """needle이 단독 토큰으로 등장하는지(앞뒤에 한글·영숫자 등이 바로 붙지 않음)."""
    if not text or not needle:
        return False
    nlen = len(needle)
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx == -1:
            return False
        left_ok = idx == 0 or not _is_word_gluing_char(text[idx - 1])
        right_ok = idx + nlen >= len(text) or not _is_word_gluing_char(text[idx + nlen])
        if left_ok and right_ok:
            return True
        start = idx + nlen


def _meta_title_matches_partner_names(title: str, names: list[str]) -> bool:
    """Meta / 메타: 단독 표기만 인정. 그 외 별칭은 부분 문자열 매칭."""
    for raw in names:
        name = (raw or "").strip()
        if not name:
            continue
        if name == "메타":
            if _has_standalone_substring(title, "메타"):
                return True
        elif name.lower() == "meta":
            if re.search(r"(?<![A-Za-z])Meta(?![A-Za-z])", title, re.IGNORECASE):
                return True
        elif name in title:
            return True
    return False


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
    if article.partner_id in _STANDALONE_KO_META_PARTNERS:
        return _meta_title_matches_partner_names(title, names)
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
