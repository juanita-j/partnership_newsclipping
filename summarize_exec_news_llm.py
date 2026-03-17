# -*- coding: utf-8 -*-
"""
news_raw.json → LLM 판별·요약 → news_summary.json

- 본문(또는 제목+요약)을 기반으로 실제 임원인사 기사인지 LLM이 판별.
- 관련 기사만 구조화된 JSON으로 요약 (회사명, 인사 유형, 대상 인물, 직책, 요약, 중요 포인트, 관련도, URL).
- 동일 인사 이벤트 중복 제거.
- 예외: 본문 추출 실패 시 제목+요약만 사용, LLM/JSON 실패 시 해당 기사 스킵, 결과 0건 시 빈 배열 저장.
"""
import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone

OUTPUT_DIR = Path(__file__).resolve().parent
NEWS_RAW_JSON = OUTPUT_DIR / "news_raw.json"
NEWS_SUMMARY_JSON = OUTPUT_DIR / "news_summary.json"
DEBUG_SUMMARY_JSON = OUTPUT_DIR / "debug_summary.json"

# LLM 출력 스키마. is_exec_news=true 이면 포함(임원인사 또는 조직개편 또는 둘 다).
# category_flags: exec_personnel(임원인사), org_restructuring(주요 조직개편). 둘 다 해당 가능.
# org_changes: 조직개편만 있을 때도 채움. 본부/실/센터/사업부/부문 단위.
SUMMARY_SCHEMA = """
{
  "is_exec_news": true | false,
  "reason": "판별 이유 한 줄 (제외 시에만)",
  "category_flags": { "exec_personnel": true|false, "org_restructuring": true|false },
  "company": "회사명",
  "personnel_type": "인사 유형 (임원인사 해당 시)",
  "person_name": "대상 인물 이름",
  "previous_role": "기존 직책 (불명이면 빈 문자열)",
  "new_role": "신규 직책 (불명이면 빈 문자열)",
  "org_changes": ["조직개편 내용1", "조직개편 내용2"],
  "summary_2sent": "2문장 요약",
  "key_points": ["중요 포인트1", "중요 포인트2"],
  "bullet_points": ["브리핑 문장 또는 (경력: 직책1, 직책2)", "..."],
  "relevance_score": 1-5,
  "article_url": "기사 URL"
}
"""

SYSTEM_PROMPT = """당신은 한국 기업의 **임원인사**와 **주요 조직개편** 뉴스를 분류·요약하는 전문가입니다.

[포함할 기사] 두 범주 중 하나 이상 해당 시 포함.
1) 임원인사: 대표이사·사장·부사장·전무·상무 선임/영입/승진/이동/사임, 사내·사외이사 연임/연임 포기/교체, 이사회 개편
2) 주요 조직개편: 본부/실/센터/사업부/부문 신설·통합·폐지·개편·재편, 조직 슬림화·통폐합, TFT/전담조직 신설, AI·글로벌 조직 강화, 자회사/법인 단위 재편. **조직개편만 있는 기사도 포함.**

본문이 없어도 제목+요약만으로 판별 가능. 회사 차원의 주요 조직만 포함(본부·실·센터·사업부·부문·위원회·전사/자회사 단위).

[반드시 제외할 기사]
- 스포츠 선수 영입·이적, 연예인·홍보대사 영입, 연봉·보수 공시
- 단순 인력 충원, 일반 채용 확대
- 행사성 TF, 프로젝트성 임시 태스크포스
- 팀/파트/셀 등 소규모 단위 변경, 단순 명칭 변경만 있는 기사
- 단순 실적 발표, 인터뷰, 전망/코멘트만 있는 기사

[관련도 점수]
- 5: 대표·사장급 명확한 선임/사임
- 3~4: 사외이사 연임 포기, 이사회 개편, 사내이사 신규 선임 등 거버넌스 인사
- 1~2: 인사변동이 불명확하거나 단순 언급만 → is_exec_news: false 권장

[category_flags] exec_personnel: 임원인사 해당 여부. org_restructuring: 주요 조직개편 해당 여부. 둘 다 true일 수 있음.
[org_changes] 조직개편 해당 시 배열로 채움. 예: ["AI전략본부 신설", "글로벌사업부 통합"]. 본부/실/센터/사업부/부문 단위만.

[bullet_points] 브리핑 스타일, 2~5개. 명사형 또는 "~함"체. 인사·조직 사실만, 논란/의견/추측 제외.
- 임원인사 예: '윤종수' 사외이사 연임 포기, '홍길동' 대표이사 내정
- 조직개편 예: AI전략본부 신설, 글로벌사업부 통합. 경력: (경력: 직책1, 직책2). 인물명은 작은따옴표(')로 감쌈.

[출력]
반드시 유효한 JSON 한 덩어리만 출력. 앞뒤 설명·마크다운 없이."""

USER_PROMPT_TEMPLATE = """아래 뉴스가 **임원인사** 또는 **주요 조직개편**(본부/실/센터/사업부 신설·통합·폐지·개편 등) 기사인지 판별해 주세요.
본문이 "(없음)"이어도 제목과 요약만으로 판단합니다. 해당 시 category_flags와 org_changes를 채우고, 아니면 is_exec_news: false와 reason만 채우세요.

제목: {title}
요약: {description}
본문(일부): {body}

[참고] 임원인사만: exec_personnel=true, org_restructuring=false. 조직개편만: exec_personnel=false, org_restructuring=true, org_changes 채움. 둘 다: 둘 다 true. 스포츠/연예/보수/채용확대/소규모 팀 변경 → 제외.

출력 형식 (이 키만 사용, JSON만 출력):
{schema}"""


def _get_openai_client():
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai 패키지가 필요합니다. pip install openai")
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경 변수가 없습니다.")
    return OpenAI(api_key=api_key)


def _build_article_text(article: dict) -> str:
    """본문 우선, 없으면 제목+요약."""
    body = (article.get("body") or "").strip()
    if body and len(body) > 50:
        return body[:4000]
    title = (article.get("title") or "").strip()
    desc = (article.get("description") or "").strip()
    return f"{title}\n{desc}"[:2000]


def _parse_llm_response(text: str, url: str) -> tuple[dict | None, dict]:
    """
    LLM 응답 텍스트 파싱.
    반환: (summary_item 또는 None, debug_필드용 dict)
    - summary_item: is_exec_news 이고 필드 정상일 때만, 아니면 None
    - debug용: company, person, action_type, exclude_reason(비관련 시)
    """
    cleaned = re.sub(r"^```(?:json)?\s*", "", text)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    cleaned = cleaned.strip()

    company, person, action_type, exclude_reason = "", "", "", ""

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"JSON 파싱 실패 (link={url[:50]}…): {e}")
        return None, {
            "company": "",
            "person": "",
            "action_type": "",
            "exclude_reason": f"JSON 파싱 실패: {e!s}",
        }

    company = (data.get("company") or "").strip()
    person = (data.get("person_name") or "").strip()
    action_type = (data.get("personnel_type") or "").strip()
    cf = data.get("category_flags") or {}
    exec_personnel = bool(cf.get("exec_personnel"))
    org_restructuring = bool(cf.get("org_restructuring"))
    include = data.get("is_exec_news") or exec_personnel or org_restructuring
    if not include:
        exclude_reason = (data.get("reason") or "").strip() or "is_exec_news=false"
        return None, {
            "company": company,
            "person": person,
            "action_type": action_type,
            "exclude_reason": exclude_reason,
            "exec_personnel": False,
            "org_restructuring": False,
            "org_changes": [],
        }

    org_changes_raw = data.get("org_changes")
    org_changes = [str(s).strip() for s in org_changes_raw] if isinstance(org_changes_raw, list) else []
    org_changes = [s for s in org_changes if s][:15]

    bullet_points = data.get("bullet_points")
    if not isinstance(bullet_points, list):
        bullet_points = []
    bullet_points = [str(s).strip() for s in bullet_points if s][:10]

    summary = {
        "회사명": company,
        "인사 유형": action_type,
        "대상 인물": person,
        "기존 직책": (data.get("previous_role") or "").strip(),
        "신규 직책": (data.get("new_role") or "").strip(),
        "2문장 요약": (data.get("summary_2sent") or "").strip(),
        "중요 포인트": data.get("key_points") if isinstance(data.get("key_points"), list) else [],
        "bullet_points": bullet_points,
        "category_flags": {"exec_personnel": exec_personnel, "org_restructuring": org_restructuring},
        "org_changes": org_changes,
        "관련도 점수": int(data.get("relevance_score", 0)) if data.get("relevance_score") is not None else 0,
        "기사 URL": url,
    }
    return summary, {
        "company": company,
        "person": person,
        "action_type": action_type,
        "exclude_reason": "",
        "exec_personnel": exec_personnel,
        "org_restructuring": org_restructuring,
        "org_changes": org_changes,
    }


def _is_body_missing(article: dict) -> bool:
    """본문이 비어 있거나 너무 짧으면 True (제목+요약만 사용한 경우)."""
    body = (article.get("body") or "").strip()
    return len(body) <= 50


def _call_llm_once(client, article: dict) -> tuple[dict | None, dict]:
    """
    한 건 기사에 대해 LLM 호출. 최대 1회 재시도.
    반환: (summary_item 또는 None, debug_record)
    debug_record: title, is_relevant, exclude_reason, raw_llm_response, company, person, action_type, body_missing
    """
    title = (article.get("title") or "").strip()
    description = (article.get("description") or "").strip()
    body = _build_article_text(article)
    url = (article.get("link") or "").strip()
    body_missing = _is_body_missing(article)

    def make_debug(
        is_relevant: bool,
        raw: str,
        exclude_reason: str,
        company: str,
        person: str,
        action_type: str,
        exec_personnel: bool = False,
        org_restructuring: bool = False,
        org_changes: list | None = None,
    ) -> dict:
        return {
            "title": title,
            "is_relevant": is_relevant,
            "exclude_reason": exclude_reason,
            "raw_llm_response": raw,
            "company": company,
            "person": person,
            "action_type": action_type,
            "body_missing": body_missing,
            "exec_personnel": exec_personnel,
            "org_restructuring": org_restructuring,
            "org_changes": org_changes or [],
        }

    user = USER_PROMPT_TEMPLATE.format(
        title=title,
        description=description,
        body=body[:3000] if body else "(없음)",
        schema=SUMMARY_SCHEMA.strip(),
    )

    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                temperature=0.1,
                max_tokens=1024,
            )
            raw_text = (resp.choices[0].message.content or "").strip()
            summary, debug_extra = _parse_llm_response(raw_text, url)
            if summary is not None and body_missing:
                summary["요약_근거"] = "제목·요약 기반"
            return summary, make_debug(
                is_relevant=(summary is not None),
                raw=raw_text,
                exclude_reason=debug_extra.get("exclude_reason", ""),
                company=debug_extra.get("company", ""),
                person=debug_extra.get("person", ""),
                action_type=debug_extra.get("action_type", ""),
                exec_personnel=debug_extra.get("exec_personnel", False),
                org_restructuring=debug_extra.get("org_restructuring", False),
                org_changes=debug_extra.get("org_changes", []),
            )
        except Exception as e:
            print(f"LLM 호출 실패 attempt={attempt+1} (link={url[:50]}…): {e}")
            if attempt == 1:
                return None, make_debug(
                    is_relevant=False,
                    raw="",
                    exclude_reason=f"LLM 호출 실패: {e!s}",
                    company="",
                    person="",
                    action_type="",
                    exec_personnel=False,
                    org_restructuring=False,
                    org_changes=[],
                )
            import time
            time.sleep(1)
    return None, make_debug(False, "", "LLM 호출 실패(재시도 소진)", "", "", False, False, [])


def _dedupe_items(items: list[dict]) -> list[dict]:
    """동일 인사 이벤트(회사+대상 인물+유형) 중복 제거. 관련도 높은 쪽 유지."""
    if not items:
        return []
    key_to_best: dict[tuple, dict] = {}
    for it in items:
        company = (it.get("회사명") or "").strip()
        person = (it.get("대상 인물") or "").strip()
        ptype = (it.get("인사 유형") or "").strip()
        key = (company, person, ptype) if (company or person) else (it.get("기사 URL", ""),)
        existing = key_to_best.get(key)
        score = int(it.get("관련도 점수", 0))
        if existing is None or score > int(existing.get("관련도 점수", 0)):
            key_to_best[key] = it
    return list(key_to_best.values())


def main() -> int:
    if not NEWS_RAW_JSON.exists():
        print(f"오류: {NEWS_RAW_JSON} 이 없습니다. 먼저 send_exec_news_timed.py 를 실행하세요.")
        return 1

    with open(NEWS_RAW_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)

    articles = raw.get("articles") or []
    if not articles:
        payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "items": []}
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(NEWS_SUMMARY_JSON, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        with open(DEBUG_SUMMARY_JSON, "w", encoding="utf-8") as f:
            json.dump({"generated_at": datetime.now(timezone.utc).isoformat(), "articles": []}, f, ensure_ascii=False, indent=2)
        print("수집 기사 0건 → news_summary.json 빈 배열로 저장")
        return 0

    try:
        client = _get_openai_client()
    except Exception as e:
        print(f"오류: {e}")
        return 1

    items = []
    debug_records = []
    for i, art in enumerate(articles):
        result, debug_record = _call_llm_once(client, art)
        debug_records.append(debug_record)
        if result:
            result["pubDate"] = art.get("pubDate", "")
            items.append(result)
        if (i + 1) % 5 == 0 and i + 1 < len(articles):
            import time
            time.sleep(0.5)

    items = _dedupe_items(items)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_raw": str(NEWS_RAW_JSON.name),
        "items": items,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(NEWS_SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    debug_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_raw": str(NEWS_RAW_JSON.name),
        "total_articles": len(articles),
        "included_count": len(items),
        "articles": debug_records,
    }
    with open(DEBUG_SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(debug_payload, f, ensure_ascii=False, indent=2)

    print(f"요약 완료: {len(items)}건 → {NEWS_SUMMARY_JSON}")
    print(f"디버그: 기사별 처리 결과 {len(debug_records)}건 → {DEBUG_SUMMARY_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
