"""
회사별로 묶어서 HTML 메일 본문 생성.
제목 + 링크 + 3~7줄 요약.
"""
from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime

from collectors.base import Article
from collectors.date_utils import KST, format_article_mmdd
from .bracket_label import resolve_bracket_label
from filters.title_clean import clean_display_title

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
SECTIONS_FILE = CONFIG_DIR / "sections.yaml"


def load_sections() -> tuple[list[str], list[str]]:
    """(domestic partner_ids 순서, global partner_ids 순서)."""
    try:
        import yaml
        if not SECTIONS_FILE.exists():
            return [], []
        with open(SECTIONS_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        domestic = data.get("domestic") or []
        global_list = data.get("global") or []
        return list(domestic), list(global_list)
    except Exception:
        return [], []


def load_section_groups() -> tuple[list[dict], list[dict]]:
    """(domestic_groups, global_groups). 각 항목은 {name: 머릿말, partners: [partner_id, ...]}."""
    try:
        import yaml
        if not SECTIONS_FILE.exists():
            return [], []
        with open(SECTIONS_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        domestic = data.get("domestic_groups") or []
        global_list = data.get("global_groups") or []
        return list(domestic), list(global_list)
    except Exception:
        return [], []


def load_partner_display_names() -> dict[str, str]:
    """partner_id -> 표시 이름 (config의 names[0] 또는 id)."""
    try:
        import yaml
    except ImportError:
        return {}
    partners_file = CONFIG_DIR / "partners.yaml"
    if not partners_file.exists():
        return {}
    with open(partners_file, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    partners = data.get("partners") or []
    return {p["id"]: (p.get("names") or [p["id"]])[0] for p in partners if p.get("id")}


def load_partner_names_map() -> dict[str, list[str]]:
    """partner_id -> names 전체 목록 (브래킷 라벨·영문 머릿말용)."""
    try:
        import yaml
    except ImportError:
        return {}
    partners_file = CONFIG_DIR / "partners.yaml"
    if not partners_file.exists():
        return {}
    with open(partners_file, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    partners = data.get("partners") or []
    return {
        p["id"]: list(p.get("names") or [p["id"]])
        for p in partners
        if p.get("id")
    }


def headline_english_only(s: str) -> str:
    """
    그룹 머릿말에서 한글·영문이 함께 있을 때 영문 세그먼트만 남김.
    예: 구글·Google -> Google, 아마존·Amazon·AWS -> Amazon AWS
    영문이 없으면 원문 유지 (삼성, 롯데 등).
    """
    if not s or not isinstance(s, str):
        return s or ""
    s = s.strip()
    parts = re.split(r"[·,，]", s)
    eng: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if re.fullmatch(r"[A-Za-z0-9.&\s\-']+", p):
            eng.append(p)
    return " ".join(eng) if eng else s


def partner_english_headline(pid: str, names_map: dict[str, list[str]]) -> str:
    """
    파트너별 소제목(영문 브랜드 우선). names에 라틴 문자만 있는 항목을 우선 사용.
    없으면 partner_id를 타이틀 케이스로 (nexon -> Nexon).
    """
    names = names_map.get(pid) or [pid]
    for n in names:
        n = (n or "").strip()
        if not n:
            continue
        if re.fullmatch(r"[A-Za-z0-9.&\s\-']+", n):
            return n
    for n in names:
        n = (n or "").strip()
        if not n:
            continue
        if re.search(r"[A-Za-z]", n) and not re.search(r"[가-힣]", n):
            return n
    return pid.replace("_", " ").title()


def build_html(
    grouped: dict[str, list[tuple[Article, str, list]]],
    subject_date: str | None = None,
    reference_datetime: datetime | None = None,
) -> str:
    """
    grouped: { partner_id: [ (main_article, summary, all_articles), ... ] }
    subject_date: 제목에 넣을 날짜 문자열 (예: 2025-03-17)
    reference_datetime: 기사 일시 없을 때 (mm/dd) 표시용 기준 시각(KST 권장). 없으면 현재 KST.
    """
    if not subject_date:
        subject_date = datetime.now(KST).strftime("%Y-%m-%d")
    if reference_datetime is None:
        reference_datetime = datetime.now(KST)
    elif reference_datetime.tzinfo is None:
        reference_datetime = reference_datetime.replace(tzinfo=KST)
    display_names = load_partner_display_names()
    names_map = load_partner_names_map()
    domestic_groups, global_groups = load_section_groups()
    if not domestic_groups:
        domestic_ids, _ = load_sections()
        domestic_grouped = [
            (
                partner_english_headline(pid, names_map),
                [pid],
                [(pid, display_names.get(pid) or pid, grouped[pid])],
                partner_english_headline(pid, names_map),
            )
            for pid in domestic_ids
            if pid in grouped and grouped[pid]
        ]
    else:
        domestic_grouped = _build_grouped_by_headline(domestic_groups, grouped, display_names, names_map)
    if not global_groups:
        _, global_ids = load_sections()
        global_grouped = [
            (
                partner_english_headline(pid, names_map),
                [pid],
                [(pid, display_names.get(pid) or pid, grouped[pid])],
                partner_english_headline(pid, names_map),
            )
            for pid in global_ids
            if pid in grouped and grouped[pid]
        ]
    else:
        global_grouped = _build_grouped_by_headline(global_groups, grouped, display_names, names_map)
    template_file = TEMPLATES_DIR / "email.html"
    if template_file.exists():
        try:
            from jinja2 import Environment, FileSystemLoader
            env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
            env.filters["mmdd"] = lambda d: d.strftime("%m/%d") if d else ""
            env.filters["article_mmdd"] = lambda a: format_article_mmdd(a, reference_datetime)
            env.filters["sentences"] = _summary_to_sentences
            env.filters["display_title"] = clean_display_title

            def bracket_label(main_article, summary, partner_id, bracket_headline, group_partner_ids):
                return resolve_bracket_label(
                    bracket_headline,
                    partner_id,
                    main_article,
                    summary or "",
                    display_names,
                    list(group_partner_ids or []),
                )

            tpl = env.get_template("email.html")
            return tpl.render(
                date=subject_date,
                domestic_grouped=domestic_grouped,
                global_grouped=global_grouped,
                display_names=display_names,
                bracket_label=bracket_label,
            )
        except Exception:
            pass
    return _default_html(
        subject_date,
        domestic_grouped,
        global_grouped,
        display_names,
        reference_datetime,
    )


def _default_html(
    subject_date: str,
    domestic_grouped: list,
    global_grouped: list,
    display_names: dict[str, str],
    reference_datetime: datetime,
) -> str:
    """Jinja2 없을 때 기본 HTML. domestic/global_grouped = [(headline, partner_ids, [...], bracket_headline), ...]."""
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>"]
    section_style = "font-size: 1.125rem; font-weight: bold; margin-top: 24px; margin-bottom: 12px;"
    for section_label, group_list in [("I. 국내 기업", domestic_grouped), ("II. 글로벌 기업", global_grouped)]:
        if not group_list:
            continue
        parts.append(f"<p class='section-heading' style='{section_style} font-weight: bold;'>{_escape(section_label)}</p>")
        for idx, row in enumerate(group_list, 1):
            headline, group_pids, partners_with_items, bracket_headline = row
            parts.append(
                f"<p class='company-name' style='font-weight: bold;'>"
                f"<span class='company-num' style='display: inline-block; width: 2.2em; text-align: right;'>{idx}.</span> {_escape(headline)}</p>"
            )
            parts.append("<ul class='articles'>")
            for partner_id, display_name, items in partners_with_items:
                for main_article, summary, all_articles in items:
                    bracket = resolve_bracket_label(
                        bracket_headline, partner_id, main_article, summary or "", display_names, list(group_pids or [])
                    )
                    date_str = _format_article_date(main_article, reference_datetime)
                    summary_sentences = _summary_to_sentences(summary or "")
                    sub_items = "".join(f"<li>{_escape(s)}</li>" for s in summary_sentences)
                    others = [a for a in all_articles if a.url != main_article.url]
                    if others:
                        related_links = ", ".join(
                            f"<a href='{_escape(a.url)}' style='font-weight: normal;'>기사 {i}</a>"
                            for i, a in enumerate(others, 1)
                        )
                        sub_items += f"<li><span class='related-label'>관련 기사: </span>{related_links}</li>"
                    parts.append(
                        f"<li><span class='partner-label' style='font-weight: bold;'>[{_escape(bracket)}]</span> "
                        f"<a href='{_escape(main_article.url)}' style='font-weight: normal;'>{_escape(clean_display_title(main_article.title))}</a>"
                        f"{date_str}<ul class='sub-bullet'>{sub_items}</ul></li>"
                    )
            parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _build_grouped_by_headline(
    groups: list[dict],
    grouped: dict,
    display_names: dict[str, str],
    names_map: dict[str, list[str]],
) -> list[tuple]:
    """
    그룹 설정에 따라 머릿말별로 묶음.
    반환: [(display_headline, partner_ids, [(partner_id, display_name, items), ...], bracket_headline), ...]
    - display_headline: 화면에 보이는 번호 소제목 (한글·영문 혼합이면 영문만, 기타 회사는 파트너별 영문 브랜드)
    - bracket_headline: group_subsidiary_labels 매칭용 (일반 그룹은 설정의 원문 name, 기타 분리 시 파트너별 영문)
    기사가 하나라도 있는 그룹만 포함.
    """
    result: list[tuple] = []
    for g in groups:
        name = (g.get("name") or "").strip()
        pids = g.get("partners") or []
        partners_with_items = [
            (pid, display_names.get(pid) or pid, grouped[pid])
            for pid in pids
            if pid in grouped and grouped[pid]
        ]
        if not partners_with_items:
            continue
        if name == "기타 회사":
            for pid, dn, items in partners_with_items:
                ph = partner_english_headline(pid, names_map)
                result.append((ph, [pid], [(pid, dn, items)], ph))
        else:
            display = headline_english_only(name)
            result.append((display, list(pids), partners_with_items, name))
    return result


def _format_article_date(article: Article, reference_datetime: datetime) -> str:
    """기사 발표일 (mm/dd). 알 수 없으면 reference_datetime 기준."""
    mmdd = format_article_mmdd(article, reference_datetime)
    return f" <span class='article-date'>({mmdd})</span>"


def _summary_to_sentences(text: str) -> list[str]:
    """요약 텍스트를 문장 단위로 분리 (마침표·줄바꿈 기준). 각 문장 한 불릿용."""
    if not text or not isinstance(text, str):
        return []
    import re
    s = text.strip()
    if not s:
        return []
    parts = re.split(r"\.\s+|\n+", s)
    result = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if not p.endswith("."):
            p = p + "."
        result.append(p)
    return result


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
