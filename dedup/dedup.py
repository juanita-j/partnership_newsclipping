"""
유사 기사 중복 제거(dedup).
- Exact duplicate: 동일 URL, 정규화 제목 동일 → 1건만 유지
- Near duplicate: 동일 파트너 내에서 (제목+요약+본문 일부) 토큰 Jaccard 및/또는 임베딩 유사도로 후보 생성
  → LLM으로 동일 사건 판별(제목·요약·본문 발췌) → 그룹별 대표 1건만 유지
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from collectors.base import Article

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEDUP_CONFIG_FILE = CONFIG_DIR / "dedup.yaml"


def _normalize_title(title: str) -> str:
    """제목 정규화: 공백 정리, 소문자 아님(한글 유지)."""
    if not title:
        return ""
    s = re.sub(r"\s+", " ", title.strip())
    return s


def _title_tokens(title: str) -> set[str]:
    """제목을 토큰(2글자 이상 연속) 집합으로. 한글/영문 혼용."""
    s = (title or "").strip()
    tokens = set()
    # 단어 단위 + 2글자 이상 n-gram 느낌으로 간단 분리
    for part in re.findall(r"[가-힣a-zA-Z0-9]+", s):
        if len(part) >= 2:
            tokens.add(part)
        if len(part) >= 4:
            for i in range(len(part) - 1):
                tokens.add(part[i : i + 2])
    return tokens or set(s) if s else set()


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_dedup_config() -> dict:
    try:
        import yaml
        if DEDUP_CONFIG_FILE.exists():
            with open(DEDUP_CONFIG_FILE, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {
        "title_jaccard_threshold": 0.10,
        "heuristic_body_chars": 1600,
        "use_embedding_candidates": True,
        "embedding_similarity_threshold": 0.78,
        "use_llm_near_duplicate": True,
        "llm_batch_pairs": 3,
        "debug_log": True,
    }


def exact_dedup(
    pairs: list[tuple],
) -> list[tuple]:
    """
    동일 URL, 동일 정규화 제목 제거. 첫 출현만 유지.
    입력: [(Article, summary), ...]
    """
    seen_url: set[str] = set()
    seen_title: set[str] = set()
    result = []
    for article, summary in pairs:
        url = (article.url or "").strip().rstrip("/")
        if url in seen_url:
            continue
        norm_title = _normalize_title(article.title or "")
        if norm_title in seen_title:
            continue
        seen_url.add(url)
        seen_title.add(norm_title)
        result.append((article, summary))
    return result


def _heuristic_text(article: Article, summary: str, body_max: int) -> str:
    """제목+요약+본문 앞부분 — 서로 다른 제목이라도 본문에서 같은 사건 후보를 잡기 위함."""
    return (
        f"{article.title or ''}\n{summary or ''}\n{(article.body or '')[:body_max]}"
    )


def _candidate_pairs_jaccard_same_partner(
    pairs: list[tuple[Article, str]],
    jaccard_threshold: float,
    body_chars: int,
) -> list[tuple[int, int]]:
    """같은 partner_id 내에서 (제목+요약+본문 일부) 토큰 Jaccard >= threshold인 (i,j). i < j."""
    n = len(pairs)
    tokens_list = [
        _title_tokens(_heuristic_text(pairs[i][0], pairs[i][1], body_chars)) for i in range(n)
    ]
    candidates = []
    for i in range(n):
        for j in range(i + 1, n):
            if pairs[i][0].partner_id != pairs[j][0].partner_id:
                continue
            if _jaccard(tokens_list[i], tokens_list[j]) >= jaccard_threshold:
                candidates.append((i, j))
    return candidates


def _cosine_sim(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _get_embeddings_for_texts(texts: list[str]) -> list[list[float]] | None:
    """OpenAI embeddings. 실패 시 None."""
    if not os.environ.get("OPENAI_API_KEY") or not texts:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=60.0)
        resp = client.embeddings.create(
            model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            input=texts,
        )
        return [d.embedding for d in resp.data]
    except Exception:
        return None


def _embedding_candidate_pairs_same_partner(
    pairs: list[tuple[Article, str]],
    threshold: float,
    body_chars: int,
) -> list[tuple[int, int]]:
    """파트너별로 제목+요약+본문 일부 임베딩 후 코사인 유사도 >= threshold 인 쌍."""
    by_partner: dict[str, list[int]] = {}
    for i, (a, _) in enumerate(pairs):
        by_partner.setdefault(a.partner_id, []).append(i)

    out: list[tuple[int, int]] = []
    for _pid, indices in by_partner.items():
        if len(indices) < 2:
            continue
        texts = [
            _heuristic_text(pairs[i][0], pairs[i][1], body_chars)[:8000]
            for i in indices
        ]
        emb = _get_embeddings_for_texts(texts)
        if not emb or len(emb) != len(indices):
            continue
        m = len(indices)
        for ii in range(m):
            for jj in range(ii + 1, m):
                if _cosine_sim(emb[ii], emb[jj]) >= threshold:
                    a, b = indices[ii], indices[jj]
                    if a < b:
                        out.append((a, b))
                    else:
                        out.append((b, a))
    return out


def _merge_candidate_pairs(*lists: list[tuple[int, int]]) -> list[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    merged: list[tuple[int, int]] = []
    for lst in lists:
        for i, j in lst:
            if i > j:
                i, j = j, i
            key = (i, j)
            if key not in seen:
                seen.add(key)
                merged.append(key)
    return merged


def _union_find_groups(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    """edges로 연결된 노드들을 그룹(리스트)로 반환."""
    parent = list(range(n))

    def find(x: int) -> int:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i, j in edges:
        union(i, j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        r = find(i)
        if r not in groups:
            groups[r] = []
        groups[r].append(i)
    return list(groups.values())


def _pick_representative(
    pairs: list,
    indices: list[int],
) -> int:
    """
    그룹 내 대표 인덱스 선택: title+summary 길이 최대, 동점 시 published_at 더 이른 쪽.
    반환: indices 중 하나의 인덱스.
    """
    def score(idx: int) -> tuple[int, float]:
        a, s = pairs[idx][0], pairs[idx][1]
        length = len(a.title or "") + len(s or "")
        pub = getattr(a, "published_at", None)
        if pub is not None and hasattr(pub, "timestamp"):
            ts = pub.timestamp()
        else:
            ts = 1e12
        return (length, -ts)

    best = indices[0]
    best_score = score(best)
    for i in indices[1:]:
        if score(i) > best_score:
            best = i
            best_score = score(i)
    return best


def near_dedup(
    pairs: list[tuple],
    config: dict | None = None,
) -> list[tuple]:
    """
    Near-duplicate: 같은 파트너 내 휴리스틱 후보 → LLM 동일 사건 판별 → 그룹별 대표 1건만 유지.
    """
    cfg = config or load_dedup_config()
    threshold = float(cfg.get("title_jaccard_threshold", 0.10))
    body_chars = int(cfg.get("heuristic_body_chars", 1600))
    use_embed = bool(cfg.get("use_embedding_candidates", True))
    embed_thr = float(cfg.get("embedding_similarity_threshold", 0.78))
    use_llm = bool(cfg.get("use_llm_near_duplicate", True))
    batch_size = int(cfg.get("llm_batch_pairs", 3))
    debug = bool(cfg.get("debug_log", True))

    if len(pairs) <= 1:
        return pairs

    jac_pairs = _candidate_pairs_jaccard_same_partner(pairs, threshold, body_chars)
    emb_pairs: list[tuple[int, int]] = []
    if use_embed:
        emb_pairs = _embedding_candidate_pairs_same_partner(pairs, embed_thr, body_chars)
    candidate_pairs = _merge_candidate_pairs(jac_pairs, emb_pairs)
    if debug and (jac_pairs or emb_pairs):
        print(
            f"[dedup] near 후보 쌍: Jaccard {len(jac_pairs)} + 임베딩 {len(emb_pairs)} "
            f"→ 병합 후 {len(candidate_pairs)} (partner 내)"
        )
    if not candidate_pairs:
        return pairs

    same_edges: list[tuple[int, int]] = []
    if use_llm:
        from summarizers.llm import judge_same_event_batch
        from summarizers.llm import load_config as load_llm_config
        llm_cfg = load_llm_config()
        for start in range(0, len(candidate_pairs), batch_size):
            batch = candidate_pairs[start : start + batch_size]
            batch_inputs = [
                (
                    pairs[i][0].title or "",
                    pairs[i][1] or "",
                    (pairs[i][0].body or "")[:4000],
                    pairs[j][0].title or "",
                    pairs[j][1] or "",
                    (pairs[j][0].body or "")[:4000],
                )
                for i, j in batch
            ]
            results = judge_same_event_batch(batch_inputs, llm_cfg)
            for (i, j), (is_same, _) in zip(batch, results):
                if is_same:
                    same_edges.append((i, j))
    else:
        same_edges = candidate_pairs

    groups = _union_find_groups(len(pairs), same_edges)
    repr_indices = set()
    for g in groups:
        if len(g) <= 1:
            repr_indices.add(g[0])
            continue
        r = _pick_representative(pairs, g)
        repr_indices.add(r)
        if debug:
            rep = pairs[r][0]
            tit = (rep.title or "")[:50]
            url = (rep.url or "")[:60]
            print(f"[dedup] 그룹 ({len(g)}건): 대표=[{tit}...] url={url}...")
            for i in g:
                if i != r:
                    print(f"[dedup]   제거: [{(pairs[i][0].title or '')[:50]}...]")

    result = [pairs[i] for i in range(len(pairs)) if i in repr_indices]
    return result


def dedup_articles(
    pairs: list[tuple],
    config: dict | None = None,
) -> list[tuple]:
    """
    Exact duplicate 제거 후 Near duplicate 제거.
    입력: [(Article, summary), ...] (필터+요약 이후 단계)
    출력: 중복 제거된 [(Article, summary), ...]
    """
    cfg = config or load_dedup_config()
    debug = bool(cfg.get("debug_log", True))

    before = len(pairs)
    pairs = exact_dedup(pairs)
    after_exact = len(pairs)
    if debug and before != after_exact:
        print(f"[dedup] exact 제거: {before} → {after_exact}건")

    before_near = len(pairs)
    pairs = near_dedup(pairs, cfg)
    after_near = len(pairs)
    if debug and before_near != after_near:
        print(f"[dedup] near 제거: {before_near} → {after_near}건")

    return pairs
