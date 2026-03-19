"""
회사별로 묶어서 HTML 메일 본문 생성.
제목 + 링크 + 3~7줄 요약.
"""
from pathlib import Path
from datetime import datetime

from collectors.base import Article

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


def build_html(
    grouped: dict[str, list[tuple[Article, str, list]]],
    subject_date: str | None = None,
) -> str:
    """
    grouped: { partner_id: [ (main_article, summary, all_articles), ... ] }
    subject_date: 제목에 넣을 날짜 문자열 (예: 2025-03-17)
    """
    if not subject_date:
        subject_date = datetime.now().strftime("%Y-%m-%d")
    display_names = load_partner_display_names()
    domestic_groups, global_groups = load_section_groups()
    if not domestic_groups:
        domestic_ids, _ = load_sections()
        domestic_grouped = [
            (display_names.get(pid) or pid, [(pid, display_names.get(pid) or pid, grouped[pid])])
            for pid in domestic_ids if pid in grouped and grouped[pid]
        ]
    else:
        domestic_grouped = _build_grouped_by_headline(domestic_groups, grouped, display_names)
    if not global_groups:
        _, global_ids = load_sections()
        global_grouped = [
            (display_names.get(pid) or pid, [(pid, display_names.get(pid) or pid, grouped[pid])])
            for pid in global_ids if pid in grouped and grouped[pid]
        ]
    else:
        global_grouped = _build_grouped_by_headline(global_groups, grouped, display_names)
    template_file = TEMPLATES_DIR / "email.html"
    if template_file.exists():
        try:
            from jinja2 import Environment, FileSystemLoader
            env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
            env.filters["mmdd"] = lambda d: d.strftime("%m/%d") if d else ""
            env.filters["sentences"] = _summary_to_sentences
            tpl = env.get_template("email.html")
            return tpl.render(
                date=subject_date,
                domestic_grouped=domestic_grouped,
                global_grouped=global_grouped,
                display_names=display_names,
            )
        except Exception:
            pass
    return _default_html(subject_date, domestic_grouped, global_grouped, display_names)


def _default_html(
    subject_date: str,
    domestic_grouped: list,
    global_grouped: list,
    display_names: dict[str, str],
) -> str:
    """Jinja2 없을 때 기본 HTML. domestic/global_grouped = [(headline, [(partner_id, display_name, items), ...]), ...]."""
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>"]
    section_style = "font-size: 1.125rem; font-weight: bold; margin-top: 24px; margin-bottom: 12px;"
    for section_label, group_list in [("I. 국내 기업", domestic_grouped), ("II. 글로벌 기업", global_grouped)]:
        if not group_list:
            continue
        parts.append(f"<p class='section-heading' style='{section_style} font-weight: bold;'>{_escape(section_label)}</p>")
        for idx, (headline, partners_with_items) in enumerate(group_list, 1):
            parts.append(
                f"<p class='company-name' style='font-weight: bold;'>"
                f"<span class='company-num' style='display: inline-block; width: 2.2em; text-align: right;'>{idx}.</span> {_escape(headline)}</p>"
            )
            parts.append("<ul class='articles'>")
            for _pid, display_name, items in partners_with_items:
                for main_article, summary, all_articles in items:
                    date_str = _format_article_date(main_article)
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
                        f"<li><span class='partner-label' style='font-weight: bold;'>[{_escape(display_name)}]</span> "
                        f"<a href='{_escape(main_article.url)}' style='font-weight: normal;'>{_escape(main_article.title)}</a>"
                        f"{date_str}<ul class='sub-bullet'>{sub_items}</ul></li>"
                    )
            parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _build_grouped_by_headline(
    groups: list[dict],
    grouped: dict,
    display_names: dict[str, str],
) -> list[tuple]:
    """
    그룹 설정에 따라 머릿말별로 묶음.
    반환: [(group_name, [(partner_id, display_name, items), ...]), ...]
    기사가 하나라도 있는 그룹만 포함.
    """
    result = []
    for g in groups:
        name = g.get("name") or ""
        pids = g.get("partners") or []
        partners_with_items = [
            (pid, display_names.get(pid) or pid, grouped[pid])
            for pid in pids
            if pid in grouped and grouped[pid]
        ]
        if partners_with_items:
            result.append((name, partners_with_items))
    return result


def _format_article_date(article: Article) -> str:
    """기사 발표일 mm/dd 형식. 없으면 빈 문자열."""
    dt = getattr(article, "published_at", None)
    if dt is None:
        return ""
    try:
        return f" <span class='article-date'>({dt.strftime('%m/%d')})</span>"
    except Exception:
        return ""


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
