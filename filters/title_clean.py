"""
메일 등 표시용 기사 제목 정리.
원본 Article.title은 수집·필터·dedup·요약용으로 유지하고, 화면에만 적용한다.
"""
from __future__ import annotations

import re


def clean_display_title(title: str | None) -> str:
    """
    1) 마지막 ' - ' 이후(언론사·출처명으로 쓰이는 구간) 제거
    2) [] 및 그 안의 문자열 제거 (예: [종합], [단독])
    연속 공백은 하나로 합친 뒤 앞뒤 공백 제거.
    """
    if not title:
        return ""
    s = title.strip()

    # 1. 하이픈(-) 및 그 뒤 출처 (네이버 등: "…내용 - 디일렉")
    if " - " in s:
        s = s.rsplit(" - ", 1)[0].strip()

    # 2. 대괄호 블록 제거 (중첩 대비 반복)
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\[[^\]]*\]", "", s)

    s = re.sub(r"\s+", " ", s).strip()
    return s
