"""
특정 파트너 기사 수 상한: 연관도(제목·본문에 회사 별칭이 많이·길게 등장할수록 높음) + 동점 시 최신 기사 우선.
네이버 뉴스 API는 기사별 클릭수를 주지 않아 클릭 기준은 사용하지 않습니다.
"""
from __future__ import annotations

from pathlib import Path

from collectors.base import Article

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CAPS_FILE = CONFIG_DIR / "partner_article_caps.yaml"
PARTNERS_FILE = CONFIG_DIR / "partners.yaml"


def load_partner_caps() -> dict[str, int]:
    """partner_id -> 최대 기사 수."""
    try:
        import yaml
        if not CAPS_FILE.exists():
            return {}
        with open(CAPS_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        caps = data.get("caps") or {}
        return {str(k): int(v) for k, v in caps.items() if v is not None and int(v) > 0}
    except Exception:
        return {}


def _load_partner_id_to_aliases() -> dict[str, list[str]]:
    try:
        import yaml
        if not PARTNERS_FILE.exists():
            return {}
        with open(PARTNERS_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        out: dict[str, list[str]] = {}
        for p in data.get("partners") or []:
            pid = p.get("id")
            if not pid:
                continue
            names = [str(x).strip() for x in (p.get("names") or []) if str(x).strip()]
            if names:
                out[str(pid)] = names
        return out
    except Exception:
        return {}


def _relevance_score(article: Article, aliases: list[str]) -> float:
    """제목 가중 + 본문 가중 합. 짧은 별칭(2글자 미만)은 스팸 방지로 제외."""
    title = article.title or ""
    body = article.body or ""
    score = 0.0
    for alias in sorted(aliases, key=len, reverse=True):
        if len(alias) < 2:
            continue
        if alias in title:
            score += 4.0 * (len(alias) ** 0.5)
        if alias in body:
            score += 1.0 * (len(alias) ** 0.5)
    return score


def _pub_ts(a: Article) -> float:
    if a.published_at:
        return a.published_at.timestamp()
    return 0.0


def apply_partner_caps(articles: list[Article]) -> list[Article]:
    """
    caps에 있는 partner_id별로 최대 N건까지 유지.
    제거 시 연관도 점수 하위·동점 시 오래된 기사부터 제외.
    """
    caps = load_partner_caps()
    if not caps or not articles:
        return articles

    aliases_map = _load_partner_id_to_aliases()

    # 상한 초과 파트너만: 유지할 Article 객체 id 집합
    keep_ids: set[int] = set()
    for pid, limit in caps.items():
        items = [a for a in articles if a.partner_id == pid]
        # 동일 URL 중복(수집 중복) 제거 — 첫 건만 유지
        seen_url: set[str] = set()
        deduped: list[Article] = []
        for a in items:
            u = (a.url or "").strip()
            if not u or u in seen_url:
                continue
            seen_url.add(u)
            deduped.append(a)
        items = deduped
        if len(items) <= limit:
            keep_ids.update(id(a) for a in items)
            continue
        aliases = aliases_map.get(pid, [])
        # 점수 내림차순, 동점이면 최신 우선
        ranked = sorted(
            items,
            key=lambda a: (_relevance_score(a, aliases), _pub_ts(a)),
            reverse=True,
        )
        for a in ranked[:limit]:
            keep_ids.add(id(a))

    out: list[Article] = []
    for a in articles:
        pid = a.partner_id
        if pid not in caps:
            out.append(a)
        elif id(a) in keep_ids:
            out.append(a)
    return out
