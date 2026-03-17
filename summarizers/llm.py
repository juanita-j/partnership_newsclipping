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
