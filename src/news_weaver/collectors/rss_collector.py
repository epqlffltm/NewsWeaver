# src/news_weaver/collectors/rss_collector.py
"""RSS 피드를 수집해 Article 목록으로 변환한다.

피드마다 제공하는 필드와 시각 표기가 제각각이므로, 그 차이를 흡수해
파이프라인 뒷단이 다루는 단일한 표현으로 정규화하는 것이 이 모듈의 책임이다.
"""

import re
from datetime import UTC, datetime, timedelta, timezone

# RFC 822 계열 날짜 문자열의 끝에 오는 타임존 표기를 찾는다.
# 예: "+0900", "-0500", "GMT", "Z"
TIMEZONE_MARKER_PATTERN = re.compile(r"(?:[+-]\d{2}:?\d{2}|Z|[A-Z]{2,4})\s*$")

# 타임존 표기가 없는 피드는 한국 언론사 기준으로 KST로 간주한다
KST = timezone(timedelta(hours=9))


def _has_timezone_marker(published_raw: str) -> bool:
    """발행 시각 문자열에 타임존 표기가 있는지 판정한다.

    feedparser는 표기가 있을 때만 published_parsed를 UTC로 변환하므로,
    이 판정 결과에 따라 후속 처리가 달라진다.
    """
    return TIMEZONE_MARKER_PATTERN.search(published_raw) is not None


def to_utc_datetime(published_raw: str | None, published_parsed) -> datetime | None:
    """피드의 발행 시각을 타임존을 가진 UTC datetime으로 변환한다.

    한국 언론사 피드를 전제로, 타임존 표기가 없는 경우 KST로 간주한다.
    해외 소스를 추가할 때는 이 가정을 재검토해야 한다.
    """
    if published_parsed is None:
        return None

    naive = datetime(*published_parsed[:6])

    if _has_timezone_marker(published_raw or ""):
        # feedparser가 이미 UTC로 변환했다
        return naive.replace(tzinfo=UTC)

    # 원본 시각이 그대로 남아 있으므로 KST로 간주해 변환한다
    return naive.replace(tzinfo=KST).astimezone(UTC)