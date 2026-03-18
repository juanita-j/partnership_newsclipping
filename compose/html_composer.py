"""
회사별로 묶어서 HTML 메일 본문 생성.
제목 + 링크 + 3~7줄 요약.
"""
from pathlib import Path
from datetime import datetime

from collectors.base import Article

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


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
    grouped: dict[str, list[tuple[Article, str]]],
    subject_date: str | None = None,
) -> str:
    """
    grouped: { partner_id: [ (Article, summary_text), ... ] }
    subject_date: 제목에 넣을 날짜 문자열 (예: 2025-03-17)
    """
    if not subject_date:
        subject_date = datetime.now().strftime("%Y-%m-%d")
    display_names = load_partner_display_names()
    template_file = TEMPLATES_DIR / "email.html"
    if template_file.exists():
        try:
            from jinja2 import Environment, FileSystemLoader
            env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
            env.filters["mmdd"] = lambda d: d.strftime("%m/%d") if d else ""
            tpl = env.get_template("email.html")
            return tpl.render(
                date=subject_date,
                grouped=grouped,
                display_names=display_names,
                _article_summary_pairs=grouped,
            )
        except Exception:
            pass
    return _default_html(subject_date, grouped, display_names)


def _default_html(
    subject_date: str,
    grouped: dict[str, list[tuple[Article, str]]],
    display_names: dict[str, str],
) -> str:
    """Jinja2 없을 때 기본 HTML 생성."""
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>",
        f"<h1>[뉴스클리핑] 파트너사 주요 뉴스 ({subject_date})</h1>",
    ]
    for partner_id, pairs in grouped.items():
        name = display_names.get(partner_id) or partner_id
        parts.append(f"<h2>{name}</h2>")
        parts.append("<ul class='articles'>")
        for article, summary in pairs:
            date_str = _format_article_date(article)
            summary_esc = _escape(summary).replace("\n", "<br>\n")
            parts.append(
                f"<li><a href='{_escape(article.url)}' style='font-weight: normal;'>{_escape(article.title)}</a>"
                f"{date_str}<ul class='sub-bullet'><li class='summary'>{summary_esc}</li></ul></li>"
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
