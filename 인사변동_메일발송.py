# -*- coding: utf-8 -*-
"""
인사변동 업데이트 메일 발송.
- 제목: 인사변동 업데이트 (yy/mm/dd)
- 본문: 임원인사 관련 기사 bullet 정리 (상위: 한줄요약+링크, 하위: 주요내용 3~5개)
"""

import re
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from 이메일발송 import send_gmail, TO, SENDER

# 오늘 날짜 yy/mm/dd
TODAY = datetime.now().strftime("%y/%m/%d")


def build_article_bullets(articles):
    """기사 리스트를 상위 bullet(한줄요약+링크) + 하위 bullet 3~5개 형태의 HTML로 만든다."""
    lines = ["<p>임원인사·선임·내정·교체·영입·사임·용퇴·체제·개편 관련 뉴스 요약입니다.</p>", "<ul>"]
    for a in articles:
        title = a.get("title", "").strip()
        link = (a.get("link") or "").strip()
        points = a.get("points", [])
        if not title:
            continue
        link_html = f' <a href="{link}">기사 보기</a>' if link else ""
        lines.append(f"  <li><strong>{title}</strong>{link_html}")
        if points:
            lines.append("    <ul>")
            for p in points[:5]:
                if p and p.strip():
                    lines.append(f"      <li>{p.strip()}</li>")
            lines.append("    </ul>")
        lines.append("  </li>")
    lines.append("</ul>")
    return "\n".join(lines)


def load_articles_from_json(path):
    """naver_news_키워드통합.json 또는 유사 JSON에서 articles 배열 로드. content를 3~5문장으로 쪼개 points로 쓴다."""
    path = Path(path)
    if not path.exists():
        return None
    import json
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get("articles", [])
    out = []
    for a in raw:
        title = (a.get("title") or "").strip()
        content = (a.get("content") or "").strip()
        link = (a.get("link") or "").strip()
        if not title and not link:
            continue
        # content를 문장 단위로 나누어 3~5개 하위 bullet으로 사용
        sentences = re.split(r"[.!?]\s+", content)
        points = [s.strip() for s in sentences if s.strip()][:5]
        if not points and content:
            points = [content[:200] + ("..." if len(content) > 200 else "")]
        out.append({"title": title, "link": link, "points": points})
    return out


# 뉴스 검색 결과 기반 샘플 (JSON 없을 때 사용). 실제로는 naver_news_키워드통합.json 사용 권장.
DEFAULT_ARTICLES = [
    {
        "title": "삼성전자, 임원 세대교체 가속…70년대생 퇴장 속 80년대생 발탁 확대",
        "link": "https://www.newsis.com/view/NISX20260311_0003543409",
        "points": [
            "조직 효율화와 사업 경쟁력 강화 과정에서 임원 인사 변동이 확대된 것으로 풀이된다.",
            "지난해 사임한 임원들은 영상디스플레이(VD), 생활가전(DA), 시스템LSI, 파운드리, 모바일경험(MX) 등 주요 사업부 소속이다.",
            "VD와 DA 사업부는 경쟁 심화와 원가 부담 영향으로 지난해 연간 실적 부담이 컸다.",
            "70년대생 임원 퇴장과 80년대생 발탁이 이어지며 세대교체가 가속화되고 있다.",
        ],
    },
    {
        "title": "연초 임원 36명 물러났다…삼성, 5년 최대 인적 개편",
        "link": "https://www.fnnews.com/news/2026031110000000000",
        "points": [
            "삼성전자가 AI 중심 산업 구조 변화에 대응하기 위해 대규모 임원 인사와 조직 재정비에 나선 것으로 파악됐다.",
            "올 초에만 36명의 임원이 자리에서 물러나 최근 5년 연초 기준 최대 규모의 인적 개편이 이뤄졌다.",
            "업계는 AI 기반 제조 혁신과 로봇·모바일 사업 경쟁력 강화를 위한 인사로 해석하고 있다.",
        ],
    },
    {
        "title": "KT 이사회, 임원 인사 완전히 손뗀다…관련 규정 삭제",
        "link": "https://n.news.naver.com/mnews/article/016/0002612502",
        "points": [
            "KT 이사회가 고위 임원 인사·조직개편 시 이사회의 심의·의결을 받도록 한 규정을 삭제한다.",
            "지난해 11월 해당 규정을 추가한 지 5개월 만에 원상복구하는 조치다.",
            "주요 주주인 국민연금이 주주권 침해를 우려해 문제를 제기한 데 따른 후속 조치로 풀이된다.",
        ],
    },
    {
        "title": "KT 31일 주총서 박윤영 대표 선임, 주총 직후 임원인사·조직개편 전망",
        "link": "https://www.businesspost.co.kr/BP?command=article_view&num=432654",
        "points": [
            "박윤영 대표 후보가 정기 주주총회에서 선임될 예정이다.",
            "주총 직후 임원 인사와 조직개편이 단행될 것으로 전망된다.",
            "KT 주요 자회사 대표 선임도 이어질 것으로 예상된다.",
        ],
    },
    {
        "title": "롯데카드, 정상호 신임 대표이사 선임…새 경영 체제 출범",
        "link": "https://www.polinews.co.kr/news/articleView.html?idxno=725280",
        "points": [
            "롯데카드가 정상호 신임 대표이사를 공식 선임하며 새 경영 체제에 들어갔다.",
            "조좌진 전 대표 사임 이후 3개월 만에 새로운 리더십 체제가 출범한 것이다.",
            "지난해 12월 대규모 고객 정보 유출 사고 이후 인사 개편이 이어졌다.",
        ],
    },
    {
        "title": "SK케미칼, 제약부문 등기임원 인사…Pharma 사업대표 등 선임",
        "link": "https://www.metroseoul.co.kr/article/20260312500504",
        "points": [
            "제약부문 마케팅·개발·전략 업무를 두루 섭렵한 인사를 Pharma 사업대표로 등기임원 선임했다.",
            "매각 논의되던 제약부문에 힘을 주는 행보로 해석된다.",
            "Pharma 부문 출신 임원을 등기임원으로 선임한 것은 최근 회사 행보를 일부 전환하는 의미로 보인다.",
        ],
    },
]


def main():
    json_path = Path(__file__).resolve().parent / "naver_news_키워드통합.json"
    articles = load_articles_from_json(json_path)
    if not articles:
        articles = DEFAULT_ARTICLES
    body_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body>
{build_article_bullets(articles)}
</body>
</html>"""
    subject = f"인사변동 업데이트 ({TODAY})"
    ok = send_gmail(to=TO, subject=subject, body=body_html, html=True)
    if ok:
        print(f"제목: {subject}")
        print(f"수신: {TO}")
        print(f"기사 수: {len(articles)}건")


if __name__ == "__main__":
    main()
