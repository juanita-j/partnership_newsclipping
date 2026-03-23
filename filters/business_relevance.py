"""
회사명은 검색에 걸렸으나 실제 그룹 사업과 무관한 기사 제외 (지역 병원·개인 상호 등).
설정: config/partner_business_relevance.yaml
"""
from __future__ import annotations

import re
from pathlib import Path

from collectors.base import Article

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
RULES_FILE = CONFIG_DIR / "partner_business_relevance.yaml"

_rules_cache: dict | None = None
_compiled_cache: dict[str, list[tuple[re.Pattern, list[str]]]] | None = None


def _load_rules() -> dict:
    global _rules_cache
    if _rules_cache is not None:
        return _rules_cache
    try:
        import yaml
        if not RULES_FILE.exists():
            _rules_cache = {}
            return _rules_cache
        with open(RULES_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _rules_cache = data if isinstance(data, dict) else {}
    except Exception:
        _rules_cache = {}
    return _rules_cache


def _get_compiled() -> dict[str, list[tuple[re.Pattern, list[str]]]]:
    """partner_id -> [(compiled_regex, business_anchors), ...] per noise pattern (one regex per pattern string)."""
    global _compiled_cache
    if _compiled_cache is not None:
        return _compiled_cache
    rules = _load_rules()
    out: dict[str, list[tuple[re.Pattern, list[str]]]] = {}
    for pid, cfg in rules.items():
        if not isinstance(cfg, dict):
            continue
        patterns = cfg.get("noise_title_patterns") or []
        anchors = [str(x).strip() for x in (cfg.get("business_anchors") or []) if str(x).strip()]
        compiled_list: list[tuple[re.Pattern, list[str]]] = []
        for p in patterns:
            p = str(p).strip()
            if not p:
                continue
            try:
                compiled_list.append((re.compile(p, re.IGNORECASE), anchors))
            except re.error:
                continue
        if compiled_list:
            out[str(pid)] = compiled_list
    _compiled_cache = out
    return _compiled_cache


def should_exclude_low_business_relevance(article: Article) -> bool:
    """
    True면 클리핑에서 제외 (상호·지역업체 등으로만 브랜드가 노출된 경우).
    """
    pid = article.partner_id or ""
    compiled_map = _get_compiled()
    entries = compiled_map.get(pid)
    if not entries:
        return False

    title = article.title or ""
    body = article.body or ""
    text = f"{title}\n{body[:6000]}"

    for pattern, anchors in entries:
        if not pattern.search(title):
            continue
        if not anchors:
            return True
        if any(a and a in text for a in anchors):
            return False
        return True
    return False


def reset_caches() -> None:
    """테스트용."""
    global _rules_cache, _compiled_cache
    _rules_cache = None
    _compiled_cache = None
