"""
LLM 기반 요약: 설정 로드 후 OpenAI/Anthropic 등으로 3~7줄 요약.
"""
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CONFIG_FILE = CONFIG_DIR / "summarizer.yaml"
TARGET_LINES = (3, 7)


def load_config() -> dict:
    try:
        import yaml
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {
        "provider": "openai",
        "openai": {"model": "gpt-4o-mini", "max_tokens": 500},
        "system_prompt": "한국어 뉴스 기사를 3줄 이상 7줄 이하로 요약해 주세요. 문장만 출력하고 번호나 불릿 없이 줄바꿈으로 구분해 주세요.",
        "max_body_chars": 6000,
    }


class BaseLLMSummarizer(ABC):
    """LLM 요약기 공통 인터페이스."""

    @abstractmethod
    def summarize(self, title: str, body: str) -> str | None:
        """기사 제목+본문을 3~7줄 요약. 실패 시 None."""
        pass


class OpenAISummarizer(BaseLLMSummarizer):
    """OpenAI Chat Completions API 요약."""

    def __init__(self, config: dict | None = None):
        self.config = config or load_config()
        cfg = self.config.get("openai") or {}
        self.model = os.environ.get("OPENAI_SUMMARY_MODEL") or cfg.get("model", "gpt-4o-mini")
        self.max_tokens = int(cfg.get("max_tokens", 500))
        self.system_prompt = (self.config.get("system_prompt") or "").strip()
        self.max_body = int(self.config.get("max_body_chars", 6000))

    def summarize(self, title: str, body: str) -> str | None:
        if not os.environ.get("OPENAI_API_KEY"):
            return None
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY"),
                timeout=60.0,
            )
            content = f"제목: {title}\n\n본문:\n{(body or '')[:self.max_body]}"
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt or "한국어 뉴스를 3~7줄로 요약해 주세요."},
                    {"role": "user", "content": content},
                ],
                max_tokens=self.max_tokens,
            )
            choice = resp.choices[0] if resp.choices else None
            if choice and choice.message and choice.message.content:
                return _normalize(choice.message.content)
        except Exception:
            pass
        return None


class AnthropicSummarizer(BaseLLMSummarizer):
    """Anthropic Claude API 요약."""

    def __init__(self, config: dict | None = None):
        self.config = config or load_config()
        cfg = self.config.get("anthropic") or {}
        self.model = os.environ.get("ANTHROPIC_SUMMARY_MODEL") or cfg.get("model", "claude-3-5-haiku-20241022")
        self.max_tokens = int(cfg.get("max_tokens", 500))
        self.system_prompt = (self.config.get("system_prompt") or "").strip()
        self.max_body = int(self.config.get("max_body_chars", 6000))

    def summarize(self, title: str, body: str) -> str | None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return None
        try:
            from anthropic import Anthropic
            client = Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY"),
                timeout=60.0,
            )
            content = f"제목: {title}\n\n본문:\n{(body or '')[:self.max_body]}"
            msg = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt or "한국어 뉴스를 3~7줄로 요약해 주세요.",
                messages=[{"role": "user", "content": content}],
            )
            text = None
            if msg.content and len(msg.content) > 0:
                block = msg.content[0]
                if hasattr(block, "text"):
                    text = block.text
            if text:
                return _normalize(text)
        except Exception:
            pass
        return None


def get_llm_summarizer(config: dict | None = None) -> BaseLLMSummarizer | None:
    """config의 provider에 맞는 LLM 요약기 반환. API 키 없으면 None."""
    cfg = config or load_config()
    provider = (cfg.get("provider") or os.environ.get("LLM_SUMMARY_PROVIDER", "openai")).strip().lower()
    if provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicSummarizer(cfg)
    if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
        return OpenAISummarizer(cfg)
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAISummarizer(cfg)
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicSummarizer(cfg)
    return None


def _normalize(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^[\d\.\-\*]+\s*", "", s, flags=re.M)
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    return "\n".join(lines[: TARGET_LINES[1]])


# --- 동일 사건 판별 (dedup용). 기존 provider/config 재사용 ---
SAME_EVENT_SYSTEM = """당신은 뉴스 기사 쌍이 동일한 사건/이벤트를 다루는지 판단하는 판별기이다.
두 기사가 같은 일(발표, 계약, 인수·합병, 규제 대응, 제품 출시, 인사, 사고 등)을 다루면 동일 사건이다.
서로 다른 언론사·완전히 다른 제목·다른 각도의 보도라도, 같은 뉴스(동일 인수건, 동일 규제, 동일 당사자)를 다루면 동일이다.
한쪽은 후속·심층 기사여도 핵심 사실(누가 무엇을 했는지)이 같으면 동일으로 본다. 날짜만 다른 같은 속보·동일 건 후속도 동일이다.
전혀 다른 사건·다른 당사자·다른 거래면 아니다.
답변 형식: 한 줄에 YES 또는 NO만 출력. 선택적으로 괄호 안에 신뢰도 0.0~1.0을 붙여도 된다. 예: YES (0.9) 또는 NO"""


DEDUP_JUDGE_SUMMARY_CHARS = 700
DEDUP_JUDGE_BODY_CHARS = 1100


def _article_excerpt_for_same_event(
    title: str, summary: str, body: str,
    summary_max: int = DEDUP_JUDGE_SUMMARY_CHARS,
    body_max: int = DEDUP_JUDGE_BODY_CHARS,
) -> str:
    return (
        f"제목: {title or ''}\n"
        f"요약: {(summary or '')[:summary_max]}\n"
        f"본문 발췌: {(body or '')[:body_max]}"
    )


def judge_same_event(
    title1: str,
    summary1: str,
    title2: str,
    summary2: str,
    config: dict | None = None,
    body1: str = "",
    body2: str = "",
) -> tuple[bool, float]:
    """
    두 기사가 동일한 사건을 다루는지 LLM으로 판별.
    기존 summarizer와 동일한 provider(OpenAI/Anthropic) 사용.
    반환: (is_same_event, confidence 0.0~1.0)
    """
    cfg = config or load_config()
    text1 = _article_excerpt_for_same_event(title1, summary1, body1)
    text2 = _article_excerpt_for_same_event(title2, summary2, body2)
    user_content = (
        "다음 두 뉴스 기사가 동일한 사건을 다루고 있는지 판단하라. 동일하면 YES, 아니면 NO.\n\n"
        f"[기사1]\n{text1}\n\n[기사2]\n{text2}"
    )

    if os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=30.0)
            cfg_openai = cfg.get("openai") or {}
            model = os.environ.get("OPENAI_SUMMARY_MODEL") or cfg_openai.get("model", "gpt-4o-mini")
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SAME_EVENT_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=50,
            )
            out = (resp.choices[0].message.content or "").strip().upper()
            return _parse_yes_no(out)
        except Exception:
            return False, 0.0
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"), timeout=30.0)
            cfg_ant = cfg.get("anthropic") or {}
            model = os.environ.get("ANTHROPIC_SUMMARY_MODEL") or cfg_ant.get("model", "claude-3-5-haiku-20241022")
            msg = client.messages.create(
                model=model,
                max_tokens=50,
                system=SAME_EVENT_SYSTEM,
                messages=[{"role": "user", "content": user_content}],
            )
            out = ""
            if msg.content and len(msg.content) > 0 and hasattr(msg.content[0], "text"):
                out = (msg.content[0].text or "").strip().upper()
            return _parse_yes_no(out)
        except Exception:
            return False, 0.0
    return False, 0.0


def judge_same_event_batch(
    pairs: list[tuple[str, str, str, str, str, str]],
    config: dict | None = None,
) -> list[tuple[bool, float]]:
    """
    여러 쌍을 한 번에 판별 (호출 횟수 절감).
    pairs: [(title1, summary1, body1, title2, summary2, body2), ...]
    반환: [(is_same, confidence), ...]
    """
    if not pairs:
        return []
    cfg = config or load_config()
    parts = []
    for i, (t1, s1, b1, t2, s2, b2) in enumerate(pairs):
        block1 = _article_excerpt_for_same_event(t1, s1, b1)
        block2 = _article_excerpt_for_same_event(t2, s2, b2)
        parts.append(f"[쌍{i+1}]\n[기사1]\n{block1}\n\n[기사2]\n{block2}")
    user_content = (
        "다음 각 쌍이 동일한 사건을 다루는지 판단하라. 동일하면 YES, 아니면 NO. "
        "각 쌍마다 한 줄에 YES 또는 NO만 순서대로 출력.\n\n"
        + "\n\n".join(parts)
    )

    if os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=90.0)
            cfg_openai = cfg.get("openai") or {}
            model = os.environ.get("OPENAI_SUMMARY_MODEL") or cfg_openai.get("model", "gpt-4o-mini")
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SAME_EVENT_SYSTEM},
                    {"role": "user", "content": user_content[:200000]},
                ],
                max_tokens=min(250, 55 * len(pairs)),
            )
            out = (resp.choices[0].message.content or "").strip()
            return _parse_yes_no_batch(out, len(pairs))
        except Exception:
            return [(False, 0.0)] * len(pairs)
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"), timeout=90.0)
            cfg_ant = cfg.get("anthropic") or {}
            model = os.environ.get("ANTHROPIC_SUMMARY_MODEL") or cfg_ant.get("model", "claude-3-5-haiku-20241022")
            msg = client.messages.create(
                model=model,
                max_tokens=min(250, 55 * len(pairs)),
                system=SAME_EVENT_SYSTEM,
                messages=[{"role": "user", "content": user_content[:200000]}],
            )
            out = ""
            if msg.content and len(msg.content) > 0 and hasattr(msg.content[0], "text"):
                out = (msg.content[0].text or "").strip()
            return _parse_yes_no_batch(out, len(pairs))
        except Exception:
            return [(False, 0.0)] * len(pairs)
    return [(False, 0.0)] * len(pairs)


def _parse_yes_no(s: str) -> tuple[bool, float]:
    s = s.upper().strip()
    conf = 0.8
    m = re.search(r"\(([0-9.]+)\)", s)
    if m:
        try:
            conf = float(m.group(1))
            conf = max(0.0, min(1.0, conf))
        except ValueError:
            pass
    return ("YES" in s[:10]), conf


def _parse_yes_no_batch(block: str, n: int) -> list[tuple[bool, float]]:
    lines = [ln.strip().upper() for ln in block.splitlines() if ln.strip()]
    if len(lines) < n and lines:
        first = lines[0].split()
        if len(first) >= n:
            lines = first[:n]
    result = []
    for i in range(n):
        if i < len(lines):
            result.append(_parse_yes_no(lines[i] if isinstance(lines[i], str) else str(lines[i])))
        else:
            result.append((False, 0.0))
    return result
