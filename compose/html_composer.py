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
    domestic_ids, global_ids = load_sections()
    domestic_grouped = [(pid, grouped[pid]) for pid in domestic_ids if pid in grouped and grouped[pid]]
    global_grouped = [(pid, grouped[pid]) for pid in global_ids if pid in grouped and grouped[pid]]
    template_file = TEMPLATES_DIR / "email.html"
    if template_file.exists():
        try:
            from jinja2 import Environment, FileSystemLoader
            env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
            env.filters["mmdd"] = lambda d: d.strftime("%m/%d") if d else ""
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
    """Jinja2 없을 때 기본 HTML. domestic/global_grouped = [(partner_id, items), ...]."""
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>"]
    section_style = "font-size: 1.125rem; font-weight: bold; margin-top: 24px; margin-bottom: 12px;"
    for section_label, group_list in [("I. 국내 기업", domestic_grouped), ("II. 글로벌 기업", global_grouped)]:
        if not group_list:
            continue
        parts.append(f"<p class='section-heading' style='{section_style}'>{_escape(section_label)}</p>")
        for partner_id, items in group_list:
            name = display_names.get(partner_id) or partner_id
            parts.append(f"<p class='company-name'>{_escape(name)}</p>")
            parts.append("<ul class='articles'>")
            for main_article, summary, all_articles in items:
                date_str = _format_article_date(main_article)
                summary_lines = [ln.strip() for ln in (summary or "").split("\n") if ln.strip()]
                sub_items = "".join(f"<li>{_escape(ln)}</li>" for ln in summary_lines)
                related = ""
                others = [a for a in all_articles if a.url != main_article.url]
                if others:
                    related_links = ", ".join(
                        f"<a href='{_escape(a.url)}' style='font-weight: normal;'>{_escape(a.title)}</a>"
                        for a in others
                    )
                    related = f" <span class='related-label'>관련 기사: </span>{related_links}"
                parts.append(
                    f"<li><a href='{_escape(main_article.url)}' style='font-weight: normal;'>{_escape(main_article.title)}</a>"
                    f"{date_str}{related}<ul class='sub-bullet'>{sub_items}</ul></li>"
                )
            parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _format_article_date(article: Article) -> str:
    """기사 발표일 mm/dd 형식. 없으면 빈 문자열."""
    dt = getattr(article, "published_at", None)
    if dt is None:
        return ""
    try:
        return f" <span class='article-date'>({dt.strftime('%m/%d')})</span>"
    except Exception:
        return ""


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
