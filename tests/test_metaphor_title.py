# PYTHONPATH=. python tests/test_metaphor_title.py
from datetime import datetime, timezone, timedelta

from collectors.base import Article
from filters.keyword_filter import (
    _contains_exclude_keywords,
    _is_metaphor_category_brand_in_title,
)

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)


def mk(title: str, pid: str = "apple") -> Article:
    return Article(
        title=title,
        url="http://x",
        source="t",
        published_at=now,
        body="",
        partner_id=pid,
    )


def main() -> None:
    t1 = "'NAS계 애플' 시놀로지, 매출 2배 성장 자신"
    assert _is_metaphor_category_brand_in_title(mk(t1)), t1

    t2 = "애플, 아이폰 17 출시 예고"
    assert not _is_metaphor_category_brand_in_title(mk(t2)), t2

    assert _contains_exclude_keywords("창립 30주년 기념 행사")
    assert _contains_exclude_keywords("기념비 산정")  # '기념' 부분일치로 제외

    print("OK")


if __name__ == "__main__":
    main()
