"""
파트너사 뉴스 클리핑 배치: 수집 → 필터 → 요약 → 메일 본문 생성 → 발송.
직전 발송 시각 이후 기사만 수집.
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# 프로젝트 루트를 path에 추가
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage.last_send import get_since_for_collect, set_last_send_at
from collectors.naver_news import NaverNewsCollector
from collectors.google_news import GoogleNewsCollector
from filters.keyword_filter import filter_articles
from summarizers.summarizer import summarize_batch
from compose.html_composer import build_html
from compose.merge_same_topic import merge_by_topic
from dedup.dedup import dedup_articles
from sender.send import send_mail


def load_partners() -> list[dict]:
    """config/partners.yaml 로드."""
    try:
        import yaml
        with open(ROOT / "config" / "partners.yaml", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("partners") or []
    except Exception:
        return []


def collect_all(since: datetime, limit_per_partner: int = 30) -> list:
    """모든 파트너에 대해 네이버(주), 구글(보조) 수집 후 합침."""
    partners = load_partners()
    naver = NaverNewsCollector()
    google = GoogleNewsCollector()
    articles = []
    # KST for comparison if needed
    since_aware = since.replace(tzinfo=timezone(timedelta(hours=9))) if since.tzinfo is None and since else since

    for p in partners:
        pid = p.get("id")
        names = p.get("names") or [pid]
        query = names[0]
        for name in names[:2]:  # 최대 2개 검색어 per partner (네이버 할당량 고려)
            q = name if name != query else query
            arts = naver.collect(q, pid, since=since_aware, limit=limit_per_partner)
            articles.extend(arts)
        # 보조: 구글 1회 (첫 이름만)
        try:
            g_arts = google.collect(query, pid, since=since_aware, limit=20)
            articles.extend(g_arts)
        except Exception:
            pass

    return articles


# 한 번에 요약할 최대 기사 수 (과다 시 GitHub Actions 등에서 타임아웃 방지, 환경변수로 오버라이드)
MAX_ARTICLES_TO_SUMMARIZE = 200
# 국내/글로벌 균형: 각 파트 최대 건수 (둘 합이 MAX 이하가 되도록, 글로벌 누락 방지)
MAX_DOMESTIC_FOR_SUMMARY = 110
MAX_GLOBAL_FOR_SUMMARY = 110


def load_section_ids() -> tuple[list[str], list[str]]:
    """(domestic partner_ids, global partner_ids) from config/sections.yaml."""
    try:
        import yaml
        with open(ROOT / "config" / "sections.yaml", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return list(data.get("domestic") or []), list(data.get("global") or [])
    except Exception:
        return [], []


def run(dry_run: bool = False, use_llm: bool = True) -> bool:
    """
    배치 1회 실행.
    dry_run: True면 수집·필터·요약·HTML 생성만 하고 발송하지 않음.
    use_llm: True면 LLM으로 요약(설정/API 키에 따라 OpenAI 또는 Anthropic), False면 규칙 기반만.
    """
    import os
    since = get_since_for_collect()
    print(f"[배치] 수집 시작 시점: {since}")

    articles = collect_all(since)
    print(f"[배치] 수집 건수: {len(articles)}")

    filtered = filter_articles(articles)
    print(f"[배치] 키워드 필터 후: {len(filtered)}")

    if not filtered:
        print("[배치] 발송할 기사 없음. 종료.")
        return True

    domestic_ids, global_ids = load_section_ids()
    domestic_set = set(domestic_ids)
    global_set = set(global_ids)
    domestic_articles = [a for a in filtered if a.partner_id in domestic_set]
    global_articles = [a for a in filtered if a.partner_id in global_set]

    max_dom = int(os.environ.get("MAX_DOMESTIC_FOR_SUMMARY", MAX_DOMESTIC_FOR_SUMMARY))
    max_glob = int(os.environ.get("MAX_GLOBAL_FOR_SUMMARY", MAX_GLOBAL_FOR_SUMMARY))
    to_summarize = domestic_articles[:max_dom] + global_articles[:max_glob]
    if len(filtered) > len(to_summarize):
        print(f"[배치] 요약 상한 적용: 국내 {len(domestic_articles)}→{min(len(domestic_articles), max_dom)}건, 글로벌 {len(global_articles)}→{min(len(global_articles), max_glob)}건")

    summarized = summarize_batch(to_summarize, use_llm=use_llm)
    # 유사 기사 중복 제거 (exact + near duplicate)
    summarized = dedup_articles(summarized)
    # 회사별 그룹핑 + 동일 제목 기사는 하나만 유지
    grouped_raw: dict[str, list] = {}
    for article, summary in summarized:
        pid = article.partner_id
        if pid not in grouped_raw:
            grouped_raw[pid] = []
        title_key = (article.title or "").strip()
        if any((a.title or "").strip() == title_key for a, _ in grouped_raw[pid]):
            continue
        grouped_raw[pid].append((article, summary))

    # 동일 주제 기사 하나의 불릿으로 병합 (임베딩 유사도)
    grouped: dict[str, list] = {}
    for pid, pairs in grouped_raw.items():
        grouped[pid] = merge_by_topic(pairs)

    subject_date = datetime.now(timezone(timedelta(hours=9))).strftime("%y/%m/%d")
    html = build_html(grouped, subject_date=subject_date)
    subject = f"[뉴스클리핑] 파트너사 주요 뉴스 ({subject_date})"

    if dry_run:
        print("[배치] dry_run: 발송 생략. HTML 길이:", len(html))
        return True

    ok = send_mail(to=[], subject=subject, body_html=html)
    if ok:
        set_last_send_at()
        print("[배치] 발송 완료. last_send_at 갱신.")
    else:
        print("[배치] 발송 실패. (SMTP 설정 또는 SENDER_TO 확인)")
    return ok


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    no_llm = "--no-llm" in sys.argv
    run(dry_run=dry, use_llm=not no_llm)
