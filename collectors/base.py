"""
뉴스 수집기 공통 인터페이스 및 기사 데이터 구조.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    """수집된 기사 한 건."""
    title: str
    url: str
    source: str          # 출처명 (예: 네이버 뉴스, 구글 뉴스)
    published_at: datetime | None
    body: str            # 본문 또는 요약 텍스트 (필터/요약용)
    partner_id: str      # config/partners.yaml의 id
    raw: dict = field(default_factory=dict)  # 원본 응답 보존


class BaseCollector(ABC):
    """수집기 공통 인터페이스."""

    @abstractmethod
    def collect(
        self,
        query: str,
        partner_id: str,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Article]:
        """
        검색어로 기사 수집.
        :param query: 검색어 (예: 회사명)
        :param partner_id: 파트너 ID
        :param since: 이 시각 이후 기사만 (선택)
        :param limit: 최대 건수
        :return: Article 리스트
        """
        pass
