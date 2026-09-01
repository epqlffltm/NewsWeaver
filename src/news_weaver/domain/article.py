# NewsWeaver/src/news_weaver/domain/article.py

"""
수집된 기사 하나를 표현하는 도메인 모델.

RSS, 공공데이터 API, 오픈 API 등 어떤 소스에서 왔든 파이프라인 뒷단은
이 표현 하나만 다룬다. 따라서 이 모듈은 DB, HTTP, feedparser 등
특정 기술에 의존하지 않는다.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Article:
    """
    정규화된 기사 하나.

    시각 필드는 모두 타임존을 가진 UTC 기준이다. 소스마다 타임존 표기
    유무가 다르므로, 변환 책임은 이 모델이 아니라 수집기에 있다.
    """

    # 소스별 수집 건수 집계와 장애 감지의 근거가 된다
    source_name: str

    title: str
    url: str

    # 정규화된 URL의 해시. 중복 판정 키이며 DB 유니크 제약이 걸린다
    url_hash: str

    # 발행 시각이 없는 소스가 있어(예: 한겨레), 정렬이 항상 기댈 수 있는
    # 시각으로서 필수 필드로 둔다
    collected_at: datetime

    published_at: datetime | None = None
    author: str | None = None
    summary: str | None = None

    # 본문을 제공하는 소스만 채운다. 대부분은 None이며,
    # 본문 추출 단계를 붙이기 전까지는 저장하지 않는다
    content: str | None = None