"""
주요 뉴스 키워드 필터: config/keywords.yaml 기준 1개 이상 포함 시 통과.
블로그 URL 제외, URL 기준 중복 제거.
제목에 파트너사명 미포함·코스피/코스닥·공시/배당/주가·특집/리포트 등
(신제품·전략·재무·사업 리스크 중심이 아닌) 관련도 낮은 기사·채용/공채/신입 뉴스 제외.
에어비앤비(airbnb)는 숙소 화제·이색 흥미 위주 기사 별도 제외.
바이트댄스(틱톡)는 기업 전략과 무관한 범죄·재판 보도 별도 제외.
오픈AI(OpenAI/ChatGPT) 파트너: 제품·경영·규제 등 **기업 보도**만 유지. 대학·기관의 도구 도입·인터뷰, 청년 고용 등 **거시 트렌드**는 제외.
연예인 일상·SNS·행사 화보 등 연예 스타일 기사 별도 제외.
신규 매장 오픈·브랜드파워·특정 채널·유통/전선 계열사명 위주 기사 별도 제외.
스포츠 구단·리그·경기 위주 기사(수원삼성 등 클럽명, K리그·EPL 등)는 제목·본문에 있으면 제외.
일부 키워드는 제목·본문 어디든 / 제목에만 있을 때 각각 제외.
회사명은 있으나 지역 병원·상호 등으로만 노출된 기사는 partner_business_relevance.yaml 로 제외.
기념·창립기념 등 기념 행사 위주 보도는 제목·본문에 '기념'이 있으면 제외.
제목에 'NAS계 애플' 등 ○○계 (브랜드) 비유 표현만 있고 주제가 다른 기업인 경우 해당 브랜드 파트너로는 제외.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from collectors.base import Article

from filters.business_relevance import should_exclude_low_business_relevance

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
    "보수",
    "급여",
    "상여금",
    "산학협력",
    "설문조사",
    "트렌드 리포트",
    "카피라이터",
    # 채용·공채 관련
    "채용",
    "공채",
    "신입",
    # 주식·주가·증권·특정 계열사/행사·투자 거래 관련 (요청 키워드)
    "주가",
    "주가의",
    "주가가",
    "주가는",
    "감원",
    "SK증권",
    "삼성증권",
    "현대화",
    "박람회",
    "현대로템",
    "현대위아",
    "LG이노텍",
    "LG화학",
    "투자자",
    "매도",
    "매수",
    "대회",
    # 금융·계열사·스포츠·사회공헌 등 (요청 키워드)
    "삼성에피스홀딩스",
    "삼성생명",
    "삼성화재",
    "삼성SDI",
    "삼성물산",
    "어워즈",
    "투자분석",
    "채권",
    "전북현대",
    "현대차증권",
    "증권",
    "기부",
    "봉사",
    "주가 상향",
    "주가 전망",
    # 매장 오픈·브랜드 지수·특정 채널·유통·전선 (요청 키워드)
    "신규 매장 오픈",
    "브랜드파워",
    "CJ온스타일",
    "CJ올리브네트웍스",
    "LS네트웍스",
    "LS전선",
    "금호현대",
    # 제목 또는 본문 한 곳이라도 포함 시 제외 (요청)
    "휴맥스",
    "한화비전",
    "한화엔진",
    "한화에어로스페이스",
    "뉴스브리핑",
    "삼성바이오로직스",
    "SK시그넷",
    "SK바사",
    "SK바이오사이언스",
    "현대해상",
    "신세계 프라퍼티",
    "신세계프라퍼티",
    "롯데오토옥션",
    "KT에스테이트",
    "삼성E&A",
    "♥",
    "신규 매장",
    "한화오션",
    "돈버는 퀴즈",
    # 기념·창립기념 등 행사 보도 (제목·본문)
    "기념",
]

# 제목에만 포함돼도 제외 (본문만 해당이면 통과)
EXCLUDE_TITLE_KEYWORDS = [
    "패키지",
    "주주총회",
    "시총",
    "시가총액",
    "고래잇",
    "주주가치",
    "사외이사",
    "사내이사",
    "베스트샵",
    "이사회",
    "의장",
    "소셜미디어",
]

EXCLUDE_TITLE_KEYWORD_VARIANTS = [
    "시가 총액",
]

# 띄어쓰기·표기 변형 (뉴스 본문에 자주 나오는 형태 — 위 키와 동일하게 제외)
# 스포츠 구단·프로리그·국제축구 (기업 사업 뉴스와 무관한 경기·선수 보도)
SPORTS_TEAM_KEYWORDS = [
    "스포츠팀",
    "K리그",
    "K 리그",
    "EPL",
    "프리미어리그",
    "프리미어 리그",
    "프로축구",
    "프로야구",
    "프로배구",
    "KBO",
    "NPB",
    "메이저리그",
    "NBA",
    "UEFA",
    "챔피언스리그",
    "월드컵경기장",
    "월드컵 경기장",
    "V-리그",
    "KOVO",
    "OGFC",
]

# 수원삼성 축구단 등 (삼성전자·계열사 사업 기사와 구분)
_SUWON_SAMSUNG_FC = re.compile(
    r"수원\s*삼성(?!전자|SDS|물산|생명|화재|SDI|바이오|디스플레이|반도체|증권|웰스토리)",
    re.IGNORECASE,
)

EXCLUDE_KEYWORD_VARIANTS = [
    "CJ 온스타일",
    "cj온스타일",
    "CJ 올리브네트웍스",
    "LS 네트웍스",
    "LS 전선",
    "브랜드 파워",
    "SK 바사",
    "SK 바이오사이언스",
    "SK 시그넷",
    "삼성 E&A",
    "돈 버는 퀴즈",
]


def _normalize_for_exclusion(text: str) -> str:
    """NFKC·제로폭·NBSP 제거 후 비교 (동일 문구인데 유니코드만 다른 경우 대응)."""
    t = unicodedata.normalize("NFKC", text or "")
    return t.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")


# 제목+본문에서 제외: '주가'(EXCLUDE_KEYWORDS), '주식'(단 '주식회사' 법인표기는 통과), '주주총회'
_EXCLUDE_STOCK_WORD = re.compile(r"주식(?!회사)")

# 제목·본문에서 단어 경계로만 인정할 파트너 id (현재: 메타 — '메타비아'·'메타세쿼이아' 등 제외)
_STANDALONE_KO_META_PARTNERS = frozenset({"meta"})

# 저관련도 유통/리테일성 공지 기사(매장 오픈·브랜드 입점·편성 확대 등) 제목 패턴
LOW_RELEVANCE_TITLE_PATTERNS = [
    r"오프라인\s*스토어",
    r"스토어\s*오픈",
    r"신규\s*매장",
    r"매장\s*오픈",
    r"단독\s*오픈",
    r"신규\s*브랜드",
    r"브랜드\s*입점",
    r"본격\s*선봬",
    r"선보여",
    r"신상품\s*편성",
]

# [브리프]·外 형태의 브랜드 단순 나열형 제목 판별
LISTICLE_TITLE_HINTS = ("[브리프]", "브리프", "外")

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
        "ChatGPT", "OpenAI", "Gemini", "Claude", "Perplexity", "DeepSeek", "Anthropic", "Copilot", "LLM", "생성형 AI",
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
    """파트너사명이 제목에 들어가 있으면 True."""
    names = partner_names.get(article.partner_id) or []
    if not names:
        return True
    title = article.title or ""
    if article.partner_id in _STANDALONE_KO_META_PARTNERS:
        return _meta_title_matches_partner_names(title, names)
    return any(name in title for name in names)


def _is_low_relevance_store_news(title: str, body: str) -> bool:
    """매장 오픈/브랜드 입점 위주 공지성 기사 제외."""
    t = _normalize_for_exclusion(title or "")
    b = _normalize_for_exclusion(body or "")
    head = f"{t}\n{b[:1200]}"
    return any(re.search(p, head, re.IGNORECASE) for p in LOW_RELEVANCE_TITLE_PATTERNS)


def _is_brand_listicle_title(title: str) -> bool:
    """
    [브리프]처럼 브랜드명만 길게 나열된 제목 제외.
    예: '[브리프] A B C D ...'
    """
    t = _normalize_for_exclusion(title or "")
    if not t:
        return False
    has_hint = any(h in t for h in LISTICLE_TITLE_HINTS)
    if not has_hint:
        return False
    # 완성형 한글/영문 토큰이 다수이고, 동사형 어미·구두점이 거의 없는 경우
    tokens = [x for x in re.split(r"\s+", t) if x]
    if len(tokens) < 5:
        return False
    # '출시/체결/확대' 등 행위 서술이 없고 브랜드 나열형이면 제외
    action_words = ("출시", "체결", "확대", "인수", "실적", "오픈", "선봬", "선보여", "발표")
    if any(w in t for w in action_words):
        return False
    return True


def _text_matches_keyword_lists(
    text: str,
    keywords: list[str],
    variants: list[str],
) -> bool:
    """제목 또는 본문 등 주어진 문자열에 키워드·변형이 포함되면 True."""
    t_raw = text or ""
    t = _normalize_for_exclusion(t_raw)
    for kw in keywords + variants:
        if kw in t_raw:
            return True
        if kw in t:
            return True
        kn = _normalize_for_exclusion(kw)
        if kn in t:
            return True
    return False


def _contains_exclude_keywords(text: str) -> bool:
    """제목+본문 기준 제외 키워드(코스피/특정 계열사 등)가 포함되면 True."""
    if _text_matches_keyword_lists(text, EXCLUDE_KEYWORDS, EXCLUDE_KEYWORD_VARIANTS):
        return True
    t = _normalize_for_exclusion(text or "")
    if _EXCLUDE_STOCK_WORD.search(t):
        return True
    return False


def _contains_title_exclude_keywords(title: str) -> bool:
    """제목에만 적용되는 제외 키워드(주총·시총·이사회 등)가 포함되면 True."""
    return _text_matches_keyword_lists(title, EXCLUDE_TITLE_KEYWORDS, EXCLUDE_TITLE_KEYWORD_VARIANTS)


def _is_airbnb_trivial_sensational(article: Article) -> bool:
    """
    에어비앤비(airbnb) 파트너 기사 중, 신기술·신사업·전략이 아닌
    숙소 화제·공포/이색 체험·바이럴 흥미 위주 기사 제외.
    """
    if article.partner_id != "airbnb":
        return False
    title = article.title or ""
    body = article.body or ""
    t = f"{title}\n{body}"
    tl = t.lower()

    # 숙소 내 '숨겨진 공간/방' 류 화제 기사
    if "숨겨진 공간" in t or "숨겨진 방" in t:
        return True
    if "천장 위" in t and "또 다른 방" in t:
        return True
    # 공포 영화 비유 + 숙박 맥락
    if "공포 영화" in t or "공포영화" in t:
        if any(x in t for x in ("숙소", "숙박", "에어비앤비")) or "airbnb" in tl:
            return True
    return False


def _openai_has_corporate_strategy_signals(text: str) -> bool:
    """
    OpenAI(기업) 제품·경영·규제·파트너십 등 보도로 볼 만한 신호.
    이 중 하나라도 있으면 '단순 도입·트렌드' 제외 로직을 적용하지 않음.
    """
    t = text or ""
    if re.search(r"(샘\s*알트먼|Sam\s+Altman|\bAltman\b)", t, re.I):
        return True
    if re.search(r"\b(GPT-5|GPT-4\.5|GPT-4o|GPT-4\.1|o3-mini|o4-mini|\bo3\b|\bo4\b)", t, re.I):
        return True
    if re.search(r"(소라|Sora).{0,40}(OpenAI|오픈AI)|(OpenAI|오픈AI).{0,40}(소라|Sora)", t, re.I):
        return True
    if re.search(
        r"(오픈AI|OpenAI).{0,120}(발표|출시|공개|투자|인수|합병|규제|소송|반독점|실적|매출|영업|IPO|상장|파트너십|협력|계약|탑재|\bAPI\b|Enterprise|엔터프라이즈)",
        t,
        re.I,
    ):
        return True
    if re.search(
        r"(발표|출시|공개).{0,60}(오픈AI|OpenAI|ChatGPT|GPT-5|GPT-4)",
        t,
        re.I,
    ):
        return True
    if re.search(
        r"(Microsoft|마이크로소프트|MS).{0,100}(OpenAI|오픈AI)|(OpenAI|오픈AI).{0,100}(Microsoft|마이크로소프트|MS\b)",
        t,
        re.I,
    ):
        return True
    return False


def _openai_education_or_institution_tool_noise(text: str, title: str) -> bool:
    """대학·교육기관이 ChatGPT 등을 '도입·구독'하는 보도 — 기업 전략 뉴스 아님."""
    if _openai_has_corporate_strategy_signals(text):
        return False
    tit = title or ""
    # 시리즈 대학 인터뷰·교육 혁신 특집 (제목 또는 본문 머리)
    if (
        "[첨단" in tit
        or "[첨단" in text
        or "대학들]" in tit
        or "인재양성에 주력하는 대학" in text
    ):
        return True
    if "총장" in text and "인터뷰" in text:
        if any(x in text for x in ("대학교", "여대", "대학 ", "캠퍼스", "교육혁신", "커리큘럼", "학과")):
            return True
    if "AI 융합교육" in text or "AI융합교육" in text:
        if any(x in text for x in ("캠퍼스", "학과", "전공", "대학")):
            return True
    if re.search(r"ChatGPT|챗GPT", text) and any(x in text for x in ("구독", "유료 버전", "크레딧")):
        if any(x in text for x in ("학생", "대학", "교육", "캠퍼스", "수업", "강의")):
            return True
    if "AI 리터러시" in text or "덕성 AI" in text:
        if "대학" in text or "캠퍼스" in text or "총장" in text:
            return True
    return False


def _openai_macro_labor_or_trend_noise(text: str, title: str) -> bool:
    """청년 실업·고용 구조 등 거시 트렌드 기사에서 ChatGPT만 인용하는 경우."""
    if _openai_has_corporate_strategy_signals(text):
        return False
    tit = (title or "").lower()
    combined = ((title or "") + "\n" + (text or "")).lower()

    if not ("chatgpt" in combined or "openai" in combined or "챗gpt" in combined or "오픈ai" in combined):
        return False

    # 영문: 청년 취업 일반론 (사용자 예시 2 유형)
    if re.search(
        r"young people|land jobs|job search|unemployment|entry-level|junior-level|job seeker",
        tit,
        re.I,
    ):
        return True

    if "bank of korea" in combined or "한국은행" in (text or ""):
        if re.search(r"unemploy|실업|고용|청년|일자리|position|job|hiring|recruit|감소|사라", combined, re.I):
            return True

    if re.search(r"ministry of.*stat|통계청|고용.*구조|hiring slowdown|labor market", combined, re.I):
        if re.search(r"disappear|사라진|줄어든|감소한|청년.*일자리", combined, re.I):
            return True

    return False


def _is_openai_non_corporate_tool_or_trend_news(article: Article) -> bool:
    """
    OpenAI 파트너 기사 중, 기업 전략·제품이 아니라
    (1) 타 기관의 ChatGPT 도입·교육용 보도 (2) 거시 고용·트렌드 보도 는 제외.
    """
    if article.partner_id != "openai":
        return False
    title = article.title or ""
    body = article.body or ""
    text = _normalize_for_exclusion(f"{title}\n{body}")

    if _openai_has_corporate_strategy_signals(text):
        return False
    if _openai_education_or_institution_tool_noise(text, title):
        return True
    if _openai_macro_labor_or_trend_noise(text, title):
        return True
    return False


def _is_bytedance_crime_court_news(article: Article) -> bool:
    """
    틱톡/바이트댄스 키워드가 있어도, 살인·유기·재판 등 범죄 사건 보도는 기업 뉴스가 아님.
    """
    if article.partner_id != "bytedance":
        return False
    title = article.title or ""
    body = article.body or ""
    t = f"{title}\n{body}"
    # 살해·유기 등 강한 범죄 표현
    if "살해" in t or "시체유기" in t:
        return True
    if "시신" in t and "유기" in t:
        return True
    # '살인'은 '살인적' 등 비범죄 용어와 구분
    if re.search(r"살인(?!적)", t) and any(
        x in t for x in ("혐의", "징역", "유기", "구속", "검찰", "선고", "재판", "피고인", "기소")
    ):
        return True
    if "징역" in t and ("선고" in t or "구형" in t or "집행유예" in t):
        return True
    return False


def _is_sports_team_news(article: Article) -> bool:
    """
    스포츠 구단·리그·경기 위주 기사 제외 (제목·본문).
    예: 수원삼성 레전드 vs OGFC, K리그·EPL 맞대결 등.
    """
    title = article.title or ""
    body = article.body or ""
    text = _normalize_for_exclusion(f"{title}\n{body}")
    if _text_matches_keyword_lists(text, SPORTS_TEAM_KEYWORDS, []):
        return True
    if _SUWON_SAMSUNG_FC.search(text):
        return True
    for phrase in ("삼성 라이온즈", "삼성라이온즈", "LG 트윈스", "LG트윈스"):
        if phrase in text:
            return True
    return False


# 제목 'NAS계 애플'·'클라우드계 구글' 등 인용부호 안 비유 (실제 주제는 뒤따르는 기업)
# 유니코드 따옴표 \u2018\u2019\u201c\u201d 포함
_QUOT_OPEN = r"[''「\"\[\(\u2018\u2019\u201c\u201d]"
_QUOT_CLOSE = r"[''」\"\]\)\u2018\u2019\u201c\u201d]"
_METAPHOR_QUOTED_CATEGORY_BRAND = {
    "apple": re.compile(
        rf"(?:{_QUOT_OPEN})[^\]\)''」\"\u2018\u2019\u201c\u201d]{{0,100}}\S+계\s*(?:애플|Apple)[^\]\)''」\"\u2018\u2019\u201c\u201d]{{0,40}}(?:{_QUOT_CLOSE})",
        re.IGNORECASE,
    ),
    "google": re.compile(
        rf"(?:{_QUOT_OPEN})[^\]\)''」\"\u2018\u2019\u201c\u201d]{{0,100}}\S+계\s*(?:구글|Google)[^\]\)''」\"\u2018\u2019\u201c\u201d]{{0,40}}(?:{_QUOT_CLOSE})",
        re.IGNORECASE,
    ),
    "meta": re.compile(
        rf"(?:{_QUOT_OPEN})[^\]\)''」\"\u2018\u2019\u201c\u201d]{{0,100}}\S+계\s*(?:메타|Meta)[^\]\)''」\"\u2018\u2019\u201c\u201d]{{0,40}}(?:{_QUOT_CLOSE})",
        re.IGNORECASE,
    ),
}
# 인용 없이: NAS계 애플, 시놀로지 … (비유 뒤 실제 주제가 다른 브랜드)
_METAPHOR_UNQUOTED_APPLE_THEN_OTHER = re.compile(
    r"\S+계\s*(?:애플|Apple)\s*[,，]\s*[^,]{0,35}(시놀로지|Synology|네이버|카카오|라인|LG|SK|현대|삼성전자)",
    re.IGNORECASE,
)
# 'NAS계 애플' 시놀로지 — 쉼표 없이 비유 직후 다른 회사명이 주제
_METAPHOR_APPLE_THEN_SYNOLOGY = re.compile(
    r"\S+계\s*(?:애플|Apple)[\s''」\u2018\u2019]{0,4}\s*(?:시놀로지|Synology)",
    re.IGNORECASE,
)


def _is_metaphor_category_brand_in_title(article: Article) -> bool:
    """
    제목에 기업명이 나와도 '○○계 애플'처럼 비유로만 쓰인 경우 제외.
    예: 'NAS계 애플' 시놀로지 → 애플 기사가 아니라 시놀로지 주제.
    """
    title = article.title or ""
    if not title.strip():
        return False
    pid = article.partner_id or ""
    pat = _METAPHOR_QUOTED_CATEGORY_BRAND.get(pid)
    if pat and pat.search(title):
        return True
    if pid == "apple":
        if _METAPHOR_UNQUOTED_APPLE_THEN_OTHER.search(title):
            return True
        if _METAPHOR_APPLE_THEN_SYNOLOGY.search(title):
            return True
    return False


def _is_entertainment_celeb_fluff(article: Article) -> bool:
    """
    연예인 일상·SNS·가족 나들이·화보·행사 포토 등 기업 뉴스와 무관한 연예 스타일 기사.
    """
    title = article.title or ""
    body = article.body or ""
    t = f"{title}\n{body}"

    # 연예 스타일 제목 (하트 이모티콘)
    if any(sym in title for sym in ("♥", "♡", "💖", "💕")):
        return True
    # SNS 보도 클리셰
    if "소셜미디어를 통해" in t:
        return True
    # '기자] 배우/가수 …' 전형적 연예 리드
    if re.search(r"기자\]\s*배우", body) or re.search(r"기자\]\s*가수", body):
        return True
    for phrase in (
        "연예계",
        "화보 촬영",
        "레드카펫",
        "팬사인회",
        "열애설",
        "결별",
        "공개 연애",
        "공개열애",
        "데일리룩",
        "행사에 참석",
        "행사 참석",
        "포토] 배우",
        "포토] 가수",
    ):
        if phrase in t:
            return True
    # 인스타 일상 게시 + 연예인 언급
    if "인스타그램" in t and any(
        x in t for x in ("게재했다", "게시했다", "사진을 올렸", "사진을 공개", "글과 함께 사진")
    ):
        if any(x in t for x in ("배우", "가수", "연예인")):
            return True
    return False


def filter_articles(articles: list[Article], keywords: list[str] | None = None) -> list[Article]:
    """
    키워드 1개 이상 포함 + 블로그 제외 + URL 중복 제거.
    + 제목에 파트너사명 미포함 제외, 제목·본문 제외 키워드·제목 전용 제외 키워드 적용.
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
        if _is_brand_listicle_title(a.title or ""):
            continue
        if _is_low_relevance_store_news(a.title or "", a.body or ""):
            continue
        if _contains_exclude_keywords((a.title or "") + " " + (a.body or "")):
            continue
        if _contains_title_exclude_keywords(a.title or ""):
            continue
        if _is_metaphor_category_brand_in_title(a):
            continue
        if _is_airbnb_trivial_sensational(a):
            continue
        if _is_bytedance_crime_court_news(a):
            continue
        if _is_openai_non_corporate_tool_or_trend_news(a):
            continue
        if _is_sports_team_news(a):
            continue
        if _is_entertainment_celeb_fluff(a):
            continue
        if should_exclude_low_business_relevance(a):
            continue
        seen_urls.add(norm_url)
        result.append(a)
    return result
