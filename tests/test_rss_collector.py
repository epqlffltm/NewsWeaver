# NewsWeaver/tests/test_rss_collector.py

"""
RSS 피드의 시각 변환이 소스별 타임존 표기 차이를 올바르게 흡수하는지 검증한다.
"""

import time
from datetime import UTC, datetime

from news_weaver.collectors.rss_collector import to_article, to_utc_datetime


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
    
COLLECTED_AT = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)


def test_to_article_maps_full_entry() -> None:
    """
    필드를 모두 제공하는 소스는 그대로 Article로 옮겨진다.
    """
    entry = {
        "title": "공기청정기 한 달 돌렸더니",
        "link": "https://zdnet.co.kr/view/?no=20260901082807",
        "published": "Tue, 01 Sep 2026 13:13:47 +0900",
        "published_parsed": time.struct_time((2026, 9, 1, 4, 13, 47, 1, 244, 0)),
        "author": "안희정 기자",
        "summary": "고효율 필터가 장착된 공기청정기를 한 달간 사용한 연구 결과가 나왔다.",
    }

    article = to_article(entry, "ZDNet", COLLECTED_AT)

    assert article is not None
    assert article.source_name == "ZDNet"
    assert article.author == "안희정 기자"
    assert article.published_at == datetime(2026, 9, 1, 4, 13, 47, tzinfo=UTC)


def test_to_article_keeps_original_url() -> None:
    """
    url에는 원본을, url_hash에는 정규화된 값의 해시를 담는다.
    """
    entry = {
        "title": "제목",
        "link": "https://zdnet.co.kr/view/?no=123&utm_source=naver",
    }

    article = to_article(entry, "ZDNet", COLLECTED_AT)

    assert article is not None
    assert article.url == "https://zdnet.co.kr/view/?no=123&utm_source=naver"


def test_to_article_handles_sparse_entry() -> None:
    """
    날짜·작성자·요약을 제공하지 않는 소스도 변환된다.
    """
    entry = {
        "title": "종부세 기본공제 12억 유지",
        "link": "https://www.hani.co.kr/arti/economy/1275687.html",
        "summary": '<table border="0px"><tr><td></td></tr></table>',
    }

    article = to_article(entry, "한겨레", COLLECTED_AT)

    assert article is not None
    assert article.published_at is None
    assert article.author is None
    assert article.summary is None
    assert article.collected_at == COLLECTED_AT


def test_to_article_rejects_entry_without_title() -> None:
    """
    제목이 없으면 요약할 대상이 없으므로 버린다.
    """
    entry = {"link": "https://example.com/article"}

    assert to_article(entry, "테스트", COLLECTED_AT) is None


def test_to_article_rejects_entry_without_link() -> None:
    """
    링크가 없으면 중복 판정이 불가능하므로 버린다.
    """
    entry = {"title": "제목만 있는 항목"}

    assert to_article(entry, "테스트", COLLECTED_AT) is None