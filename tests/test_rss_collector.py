# NewsWeaver/tests/test_rss_collector.py

"""
RSS 피드의 시각 변환이 소스별 타임존 표기 차이를 올바르게 흡수하는지 검증한다.
"""

import time
from datetime import UTC, datetime

from news_weaver.collectors.rss_collector import to_utc_datetime


def test_offset_marked_time_is_kept_as_utc() -> None:
    """
    타임존 표기가 있으면 feedparser가 이미 UTC로 바꿔놓은 값을 그대로 쓴다.
    """
    # 전자신문: "Tue, 1 Sep 2026 14:20:00 +0900" → parsed는 UTC 05:20
    parsed = time.struct_time((2026, 9, 1, 5, 20, 0, 1, 244, 0))

    result = to_utc_datetime("Tue, 1 Sep 2026 14:20:00 +0900", parsed)

    assert result == datetime(2026, 9, 1, 5, 20, tzinfo=UTC)


def test_unmarked_time_is_treated_as_kst() -> None:
    """
    타임존 표기가 없으면 KST로 간주해 UTC로 변환한다.
    """
    # 블로터: "2026-09-01 14:35:04" → parsed에 KST 14:35가 그대로 남음
    parsed = time.struct_time((2026, 9, 1, 14, 35, 4, 1, 244, 0))

    result = to_utc_datetime("2026-09-01 14:35:04", parsed)

    assert result == datetime(2026, 9, 1, 5, 35, 4, tzinfo=UTC)


def test_missing_time_returns_none() -> None:
    """
    발행 시각을 제공하지 않는 소스는 None을 반환한다.
    """
    assert to_utc_datetime(None, None) is None