# pytest 없이 실행: python tests/test_openai_filter.py
from datetime import datetime, timezone, timedelta

from collectors.base import Article
from filters.keyword_filter import _is_openai_non_corporate_tool_or_trend_news, _openai_has_corporate_strategy_signals

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)


def art(title: str, body: str) -> Article:
    return Article(
        title=title,
        url="http://example.com/x",
        source="t",
        published_at=now,
        body=body,
        partner_id="openai",
    )


def test_exclude_dukseong_interview():
    title = "‘덕성(德性) 갖춘 AI 리더’ 길러내겠다"
    body = (
        "[첨단 분야 인재양성에 주력하는 대학들] ③ 덕성여대\n"
        "민재홍 덕성여자대학교 총장 인터뷰\n"
        "… ChatGPT 유료 버전/크레딧) 지원까지 연결할 것이다."
    )
    assert _is_openai_non_corporate_tool_or_trend_news(art(title, body))


def test_exclude_youth_jobs_english():
    title = "Why is it getting harder for young people to land jobs?"
    body = (
        "A 2025 report by the Bank of Korea found that in the three years following "
        "the debut of ChatGPT, about 211,000 positions for young workers disappeared."
    )
    assert _is_openai_non_corporate_tool_or_trend_news(art(title, body))


def test_keep_openai_product_news():
    title = "OpenAI, GPT-4o 업데이트 발표"
    body = "오픈AI는 이날 블로그를 통해 신기능을 공개했다."
    assert not _is_openai_non_corporate_tool_or_trend_news(art(title, body))
    assert _openai_has_corporate_strategy_signals(title + "\n" + body)


if __name__ == "__main__":
    test_exclude_dukseong_interview()
    test_exclude_youth_jobs_english()
    test_keep_openai_product_news()
    print("OK")
