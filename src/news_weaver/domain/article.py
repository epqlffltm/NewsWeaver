# src/news_weaver/domain/article.py
"""
수집된 기사 하나를 표현하는 도메인 모델.

RSS, 공공데이터 API, 오픈 API 등 어떤 소스에서 왔든 파이프라인 뒷단은
이 표현 하나만 다룬다. 따라서 이 모듈은 DB, HTTP, feedparser 등
특정 기술에 의존하지 않는다.
"""

from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen = True, slots = True)
class Article:
    """
    정규화된 기사 하나.

    시각 필드는 모두 타임존을 가진 UTC 기준이다. 소스마다 타임존 표기
    유무가 다르므로, 변환 책임은 이 모델이 아니라 수집기에 있다.
    """
    
    source_name: str
    """기사 수집 소스 이름"""

    title: str
    """기사 제목"""
    
    url: str
    """기사 URL"""
    
    url_hash: str
    """기사 URL의 해시값. 중복 수집 방지용"""
    
    collected_at: datetime
    """기사 수집 시각. UTC 기준"""
    
    published_at: datetime | None = None
    """기사 발행 시각. UTC 기준. 소스에 따라 없을 수 있음"""
    
    author: str | None = None
    """기사 작성자. 소스에 따라 없을 수 있음"""
    
    summary: str | None = None
    """기사 요약. 소스에 따라 없을 수 있음"""
    
    content: str | None = None
    """기사 본문. 소스에 따라 없을 수 있음"""