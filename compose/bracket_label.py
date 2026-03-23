"""
메일 본문 [머릿말] 표기: 상위 그룹(sections 머릿말)은 유지하고,
기사 제목·본문·요약에 실제로 등장한 그룹사명이 있으면 그 이름을 사용.
"""
from __future__ import annotations

from pathlib import Path

from collectors.base import Article

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
LABELS_FILE = CONFIG_DIR / "group_subsidiary_labels.yaml"
PARTNERS_FILE = CONFIG_DIR / "partners.yaml"

# 매칭 후보에서 제외할 짧은 본사 브랜드(머릿말과 별개로 공통 제외)
_EXTRA_EXCLUDE_BY_HEADLINE: dict[str, frozenset[str]] = {
    "SK": frozenset({"SK"}),
    "LG": frozenset({"LG"}),
    "GS": frozenset({"GS"}),
    "CJ": frozenset({"CJ"}),
    "LS": frozenset({"LS"}),
    "KT": frozenset({"KT"}),
}

_labels_cache: dict | None = None
_partner_names_cache: dict[str, list[str]] | None = None


def _load_labels_yaml() -> dict[str, list[str]]:
    global _labels_cache
    if _labels_cache is not None:
        return _labels_cache
    try:
        import yaml
        if LABELS_FILE.exists():
            with open(LABELS_FILE, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                _labels_cache = {}
            else:
                _labels_cache = {
                    str(k): [str(x).strip() for x in (v or []) if str(x).strip()]
                    for k, v in data.items()
                }
        else:
            _labels_cache = {}
    except Exception:
        _labels_cache = {}
    return _labels_cache


def _load_partner_alias_map() -> dict[str, list[str]]:
    """partner_id -> names 리스트."""
    global _partner_names_cache
    if _partner_names_cache is not None:
        return _partner_names_cache
    try:
        import yaml
        if not PARTNERS_FILE.exists():
            _partner_names_cache = {}
            return _partner_names_cache
        with open(PARTNERS_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        partners = data.get("partners") or []
        _partner_names_cache = {
            p["id"]: list(p.get("names") or [p["id"]])
            for p in partners
            if p.get("id")
        }
    except Exception:
        _partner_names_cache = {}
    return _partner_names_cache


def _build_candidates(group_headline: str, partner_ids: list[str]) -> list[str]:
    labels = _load_labels_yaml()
    aliases = _load_partner_alias_map()

    raw: list[str] = []
    if group_headline in labels:
        raw.extend(labels[group_headline])
    for pid in partner_ids:
        raw.extend(aliases.get(pid, []))

    seen: set[str] = set()
    uniq: list[str] = []
    for x in raw:
        x = (x or "").strip()
        if not x or x in seen:
            continue
        seen.add(x)
        uniq.append(x)

    exclude: set[str] = {group_headline}
    exclude |= set(_EXTRA_EXCLUDE_BY_HEADLINE.get(group_headline, frozenset()))

    uniq = [x for x in uniq if x not in exclude]
    # 긴 문자열 우선(계열사 구분), 동일 길이면 YAML·파트너 정의 순서 유지
    order = {x: i for i, x in enumerate(uniq)}
    uniq.sort(key=lambda x: (-len(x), order[x]))
    return uniq


def resolve_bracket_label(
    group_headline: str,
    partner_id: str,
    article: Article,
    summary: str,
    display_names: dict[str, str],
    partner_ids_in_group: list[str],
) -> str:
    """
    기사 텍스트에 그룹사명이 있으면 가장 긴 매칭 문자열을 반환.
    없으면 partners.yaml 기반 표시명(display_names[partner_id]).
    """
    default_label = (display_names.get(partner_id) or partner_id).strip()
    if not partner_ids_in_group:
        return default_label

    parts = [
        article.title or "",
        article.body or "",
        summary or "",
    ]
    text = " ".join(parts)

    for candidate in _build_candidates(group_headline, partner_ids_in_group):
        if candidate and candidate in text:
            return candidate

    return default_label
