"""
동일 주제 기사를 하나의 불릿으로 병합.
OpenAI 임베딩으로 유사도 계산 후, 유사도가 높으면 한 그룹으로 묶음.
반환: [(main_article, summary, all_articles), ...] — all_articles에 해당 주제 기사 전부.
"""
import os
from typing import List, Tuple

from collectors.base import Article

# 같은 주제로 묶을 유사도 하한 (코사인 유사도)
SIMILARITY_THRESHOLD = 0.84


def _get_embeddings(texts: list[str]) -> list[list[float]] | None:
    """OpenAI embeddings. 실패 시 None."""
    if not os.environ.get("OPENAI_API_KEY") or not texts:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=30.0)
        resp = client.embeddings.create(
            model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            input=texts,
        )
        return [d.embedding for d in resp.data]
    except Exception:
        return None


def _cosine_sim(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def merge_by_topic(
    pairs: list[tuple[Article, str]],
) -> list[tuple[Article, str, list[Article]]]:
    """
    동일 주제 기사를 묶어서 반환.
    반환: [(main_article, summary, all_articles), ...]
    - main_article: 대표 기사 (제목·날짜용)
    - summary: 대표 요약문 (클러스터 내 가장 긴 요약)
    - all_articles: 해당 주제로 묶인 기사 전부 (관련 기사 링크용)
    """
    if not pairs:
        return []
    if len(pairs) == 1:
        a, s = pairs[0]
        return [(a, s, [a])]

    texts = [(a.title or "") + "\n" + (s or "") for a, s in pairs]
    embeddings = _get_embeddings(texts)
    if not embeddings or len(embeddings) != len(pairs):
        return [(a, s, [a]) for a, s in pairs]

    # 단순 클러스터링: 첫 번째를 기준으로, 유사도 >= threshold면 같은 클러스터
    clusters: list[list[int]] = []
    for i in range(len(pairs)):
        placed = False
        for c in clusters:
            if any(_cosine_sim(embeddings[i], embeddings[j]) >= SIMILARITY_THRESHOLD for j in c):
                c.append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])

    result: list[tuple[Article, str, list[Article]]] = []
    for idx_list in clusters:
        group = [pairs[i] for i in idx_list]
        main_article, main_summary = group[0]
        best_summary = max((s for _, s in group), key=lambda x: len(x or ""))
        all_articles = [a for a, _ in group]
        result.append((main_article, best_summary, all_articles))
    return result
