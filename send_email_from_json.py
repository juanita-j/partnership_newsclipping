# -*- coding: utf-8 -*-
"""
news_summary.json 을 읽어 HTML 메일로 Gmail 발송.

- 파이프라인: send_exec_news_timed.py → news_raw.json → summarize_exec_news_llm.py → news_summary.json → 본 스크립트
- sent_log.json 기반 재발송 방지: 동일 content_hash + 당일 이미 발송 시 스킵. FORCE_SEND=1 이면 무시.
- 환경 변수: GMAIL_APP_PASSWORD 필수. GMAIL_SENDER, GMAIL_TO 는 JSON 또는 env 로 덮어쓸 수 있음.
"""

import hashlib
import json
import os
import re
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parsedate_to_datetime

OUTPUT_DIR = Path(__file__).resolve().parent
NEWS_SUMMARY_JSON = OUTPUT_DIR / "news_summary.json"
SENT_LOG_JSON = OUTPUT_DIR / "sent_log.json"
# 레거시: email_content.json (직접 HTML 있는 경우)
EMAIL_CONTENT_JSON = OUTPUT_DIR / "email_content.json"


def _pubdate_to_mmdd(pub_date_str: str) -> str:
    """pubDate 문자열에서 mm/dd 추출. 실패 시 빈 문자열."""
    if not pub_date_str or not str(pub_date_str).strip():
        return ""
    try:
        dt = parsedate_to_datetime(str(pub_date_str).strip())
        return dt.strftime("%m/%d")
    except Exception:
        return ""


def _format_person_name(name: str) -> str:
    """대상 인물이 있으면 작은따옴표로 감쌈."""
    s = (name or "").strip()
    if not s:
        return s
    if s.startswith("'") and s.endswith("'"):
        return s
    return f"'{s}'"


def _title_from_key_points(key_points: list, max_len: int = 60) -> str:
    """중요 포인트에서 제목 문자열 생성. 60자 초과 시 ... 자름."""
    if not key_points:
        return ""
    first = (key_points[0] if key_points else "").strip()
    if not first:
        return ""
    if len(first) > max_len:
        return first[:max_len].rstrip() + "..."
    return first


def _to_briefing_style(s: str) -> str:
    """문장을 브리핑 스타일 명사형으로 간단 변환. (~했다→~함, ~중 등)"""
    if not s or not s.strip():
        return s
    s = s.strip()
    s = re.sub(r"했다\.?\s*$", "함", s)
    s = re.sub(r"했다\s*$", "함", s)
    s = re.sub(r"하고\s*있다\.?\s*$", "중", s)
    s = re.sub(r"되고\s*있다\.?\s*$", "중", s)
    s = re.sub(r"될\s*것으로\s*보인다\.?\s*$", "전망", s)
    return s


def _bullets_from_item(it: dict) -> list[str]:
    """bullet_points 있으면 사용(2~5개), 없으면 2문장 요약·중요 포인트로 브리핑 스타일 불렛 생성."""
    bullets = it.get("bullet_points")
    if isinstance(bullets, list) and bullets:
        return [str(b).strip() for b in bullets if str(b).strip()][:10]

    # fallback: 2문장 요약 + 중요 포인트, 브리핑 스타일로
    out = []
    summary = (it.get("2문장 요약") or "").strip()
    if summary:
        for s in re.split(r"[.;]\s+", summary):
            s = _to_briefing_style(s.strip())
            if s and len(s) > 5:
                out.append(s)
    key_points = it.get("중요 포인트") or []
    person = _format_person_name(it.get("대상 인물") or "")
    company = (it.get("회사명") or "").strip()
    ptype = (it.get("인사 유형") or "").strip()
    prev_role = (it.get("기존 직책") or "").strip()
    new_role = (it.get("신규 직책") or "").strip()

    for p in key_points:
        p = _to_briefing_style(str(p).strip())
        if p and p not in out:
            out.append(p)
    if not out and (company or person or ptype):
        if person and company:
            out.append(f"{person} {company} {prev_role or '이사'} {new_role or ptype}함")
        elif company and ptype:
            out.append(f"{company} {ptype} 관련")
    return out[:10] if out else ["요약 없음"]


def _action_line(it: dict) -> str:
    """'사람명': 인사내용 형식. 브리핑 스타일."""
    person = _format_person_name(it.get("대상 인물") or "")
    action_type = (it.get("인사 유형") or "").strip()
    prev = (it.get("기존 직책") or "").strip()
    new = (it.get("신규 직책") or "").strip()
    if prev and new:
        part = f"{prev} → {new}"
    elif prev:
        part = f"{prev} {action_type}"
    elif new:
        part = f"{new} {action_type}"
    else:
        part = action_type
    if person:
        return f"{person}: {part}"
    return part


def _build_html_from_summary(items: list[dict], subject: str) -> str:
    """회사별로 묶고, 회사당 [임원인사] / [조직개편] 섹션으로 HTML 본문 생성."""
    from collections import defaultdict
    by_company: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        company = (it.get("회사명") or "").strip() or "(회사명 없음)"
        by_company[company].append(it)

    lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>",
        f"<h2>{subject}</h2>",
        "<ul>",
    ]
    for company in sorted(by_company.keys(), key=lambda x: (x.startswith("("), x)):
        group = by_company[company]
        rep_date = ""
        rep_url = ""
        for it in group:
            if it.get("pubDate"):
                rep_date = _pubdate_to_mmdd(it.get("pubDate") or "")
            if (it.get("기사 URL") or "").strip():
                rep_url = (it.get("기사 URL") or "").strip()
            if rep_date and rep_url:
                break

        exec_items = []
        org_changes_set = set()
        exec_lines_out = []
        for it in group:
            cf = it.get("category_flags") or {}
            is_exec = cf.get("exec_personnel", True)
            is_org = cf.get("org_restructuring", False)
            if is_exec and (it.get("대상 인물") or it.get("인사 유형")):
                exec_items.append(it)
            if is_org:
                for oc in it.get("org_changes") or []:
                    if oc and str(oc).strip():
                        org_changes_set.add(str(oc).strip())
        org_changes_list = sorted(org_changes_set)

        has_exec = bool(exec_items)
        has_org = bool(org_changes_list)
        if not has_exec and not has_org:
            has_exec = True
            exec_items = group

        if has_exec and has_org:
            section_label = f"{company}, 임원인사 및 조직개편 진행"
        elif has_org:
            section_label = f"{company}, 조직개편 진행"
        else:
            section_label = f"{company}, 임원인사 진행"

        lines.append("  <li>")
        lines.append("    <p>")
        lines.append(f"      <strong>{section_label}</strong>")
        if rep_date:
            lines.append(f"      &nbsp; ({rep_date})")
        if rep_url:
            lines.append(f'      &nbsp; <a href="{rep_url}">기사 보기</a>')
        lines.append("    </p>")
        if has_exec and exec_items:
            seen_exec = set()
            exec_lines_out = []
            for it in exec_items:
                line = _action_line(it)
                if line and line not in seen_exec:
                    seen_exec.add(line)
                    exec_lines_out.append(line)
            if exec_lines_out:
                lines.append("    <p><strong>[임원인사]</strong></p>")
                lines.append("    <ul>")
                for line in exec_lines_out:
                    lines.append(f"      <li>{line}</li>")
                lines.append("    </ul>")
        if has_org and org_changes_list:
            lines.append("    <p><strong>[조직개편]</strong></p>")
            lines.append("    <ul>")
            for oc in org_changes_list:
                lines.append(f"      <li>{oc}</li>")
            lines.append("    </ul>")
        if has_exec and exec_items and not exec_lines_out and not org_changes_list:
            bullets = _bullets_from_item(group[0])
            if bullets:
                lines.append("    <ul>")
                for b in bullets:
                    lines.append(f"      <li>{b}</li>")
                lines.append("    </ul>")
        lines.append("  </li>")
    lines.append("</ul></body></html>")
    return "\n".join(lines)


def _content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _should_skip_send(body: str) -> bool:
    """sent_log 와 비교해 동일 내용·당일 이미 발송이면 True."""
    if os.environ.get("FORCE_SEND", "").strip() == "1":
        return False
    if not SENT_LOG_JSON.exists():
        return False
    try:
        with open(SENT_LOG_JSON, "r", encoding="utf-8") as f:
            log = json.load(f)
    except Exception:
        return False
    h = _content_hash(body)
    if log.get("content_hash") != h:
        return False
    last = log.get("last_sent_at")
    if not last:
        return False
    try:
        # ISO 형식 파싱 후 KST 당일 여부 확인 (간단히 날짜 문자열 비교)
        dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        from datetime import timedelta
        now_utc = datetime.now(timezone.utc)
        if (now_utc - dt).total_seconds() < 3600 * 24:  # 24시간 이내 동일 내용
            return True
    except Exception:
        pass
    return False


def send_gmail_from_json(
    json_path: Path | None = None,
    password: str | None = None,
    sender: str | None = None,
):
    if json_path is None:
        json_path = NEWS_SUMMARY_JSON if NEWS_SUMMARY_JSON.exists() else EMAIL_CONTENT_JSON
    if not json_path.exists():
        print(f"오류: {json_path} 파일이 없습니다. summarize_exec_news_llm.py 를 먼저 실행하세요.")
        return 1

    password = (password or os.environ.get("GMAIL_APP_PASSWORD") or "").replace(" ", "").strip()
    if not password:
        print("오류: GMAIL_APP_PASSWORD 환경 변수가 없습니다.")
        return 1

    # news_summary.json 우선
    items = []
    if json_path == NEWS_SUMMARY_JSON and json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        items = payload.get("items") or []
        if not items:
            print("요약 항목 0건. 메일 발송 스킵.")
            return 0
        subject = f"인사변동 업데이트 ({datetime.now().strftime('%y/%m/%d')})"
        body = _build_html_from_summary(items, subject)
        to = os.environ.get("GMAIL_TO", "juan.jung@navercorp.com").strip()
    else:
        # 레거시: email_content.json (to, subject, body, contentType)
        with open(json_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        to = payload.get("to", "").strip() or os.environ.get("GMAIL_TO", "juan.jung@navercorp.com")
        subject = payload.get("subject", "").strip()
        body = payload.get("body", "").strip()
        if payload.get("contentType", "html").lower() != "html":
            body = f"<pre>{body}</pre>"

    if not subject or not body:
        print("오류: subject 또는 body가 비어 있습니다.")
        return 1

    if _should_skip_send(body):
        print("동일 내용이 24시간 이내 이미 발송됨. 발송 스킵. (FORCE_SEND=1 로 재발송 가능)")
        return 0

    sender = (sender or os.environ.get("GMAIL_SENDER", "wjdwndks99@gmail.com")).strip()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.attach(MIMEText(body, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls(context=context)
            server.login(sender, password)
            server.sendmail(sender, to, msg.as_string())
    except Exception as e:
        print(f"Gmail 발송 실패: {e}")
        return 1

    # 발송 이력 저장
    try:
        log = {
            "last_sent_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": _content_hash(body),
            "item_count": len(items),
            "subject": subject,
        }
        with open(SENT_LOG_JSON, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"sent_log 저장 경고: {e}")

    print(f"발송 완료: {to} / 제목: {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(send_gmail_from_json())
