"""
기사 요약: LLM을 기본으로 사용하고, 실패 시에만 규칙 기반 폴백.
"""
import re
from collectors.base import Article

from .llm import get_llm_summarizer, load_config

# 캐시: url -> 요약문 (같은 기사 재요약 방지)
_summary_cache: dict[str, str] = {}
MAX_CACHE_SIZE = 2000
TARGET_LINES = (3, 7)
MAX_LINE_CHARS = 120


def summarize_article(article: Article, use_llm: bool = True) -> str:
    """
    기사 한 건을 3~7줄로 요약.
    use_llm=True면 설정된 LLM(OpenAI/Anthropic 등) 사용, 실패 시 규칙 기반 폴백.
    use_llm=False면 폴백만 사용.
    """
    if article.url in _summary_cache:
        return _summary_cache[article.url]

    text = (article.title + "\n\n" + article.body).strip()
    if not text:
        out = article.title or "(제목 없음)"
    else:
        out = None
        if use_llm:
            summarizer = get_llm_summarizer(load_config())
            if summarizer:
                out = summarizer.summarize(article.title, article.body)
        if out is None:
            out = _fallback_summary(text)

    if len(_summary_cache) < MAX_CACHE_SIZE:
        _summary_cache[article.url] = out
    return out


def _fallback_summary(text: str) -> str:
    """LLM 미사용/실패 시: 본문에서 문장 단위로 잘라 3~7줄로 제한."""
    lines: list[str] = []
    for raw in re.split(r"[\n.。]+", text):
        line = raw.strip()
        if not line or len(line) < 5:
            continue
        if len(line) > MAX_LINE_CHARS:
            line = line[: MAX_LINE_CHARS - 3] + "..."
        lines.append(line)
        if len(lines) >= TARGET_LINES[1]:
            break
    if len(lines) < TARGET_LINES[0] and text:
        single = text.replace("\n", " ").strip()[: 80 * TARGET_LINES[1]]
        if single:
            lines = [single]
    return "\n".join(lines[: TARGET_LINES[1]]) if lines else text[:500] or "(요약 없음)"


def summarize_batch(articles: list[Article], use_llm: bool = True) -> list[tuple[Article, str]]:
    """여러 기사 요약. (Article, summary_text) 리스트 반환. 기본은 LLM 사용."""
    return [(a, summarize_article(a, use_llm=use_llm)) for a in articles]
