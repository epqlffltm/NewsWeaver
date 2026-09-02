# NewsWeaver/tests/test_rss_collector.py

"""
RSS 수집기가 소스별 형식 차이와 피드 장애를 올바르게 처리하는지 검증한다.
"""

import time
from datetime import UTC, datetime

from news_weaver.collectors.rss_collector import (
    collect_all_feeds,
    collect_feed,
    to_article,
    to_utc_datetime,
)
from news_weaver.collectors.sources import RssSource

COLLECTED_AT = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)


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


def test_updated_is_used_when_published_missing() -> None:
    """
    published가 없고 updated만 있는 소스도 발행 시각을 얻는다.

    경향신문처럼 updated만 제공하는 피드가 있어, 이를 놓치면 발행 시각이
    없는 기사로 취급된다.
    """
    entry = {
        "title": "제목",
        "link": "https://example.com/1",
        "updated": "2026-09-02T15:35:00+09:00",
        "updated_parsed": time.struct_time((2026, 9, 2, 6, 35, 0, 2, 245, 0)),
    }

    article = to_article(entry, "경향신문", COLLECTED_AT)

    assert article is not None
    assert article.published_at == datetime(2026, 9, 2, 6, 35, tzinfo=UTC)


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


def test_collect_feed_marks_empty_feed_as_unhealthy(monkeypatch) -> None:
    """항목이 하나도 없으면 장애로 표시한다. 조용한 실패를 감지하기 위함이다."""

    def fake_parse(url):
        return {"entries": [], "bozo_exception": "syntax error"}

    monkeypatch.setattr(
        "news_weaver.collectors.rss_collector.feedparser.parse", fake_parse
    )

    result = collect_feed("연합뉴스", "https://example.com/rss", COLLECTED_AT)

    assert result.is_healthy is False
    assert result.article_count == 0
    assert "syntax error" in result.error


def test_collect_feed_counts_skipped_entries(monkeypatch) -> None:
    """변환할 수 없는 항목은 버리되 몇 건인지 기록한다."""

    def fake_parse(url):
        return {
            "entries": [
                {"title": "정상 기사", "link": "https://example.com/1"},
                {"title": "링크 없음"},
                {"link": "https://example.com/3"},
            ]
        }

    monkeypatch.setattr(
        "news_weaver.collectors.rss_collector.feedparser.parse", fake_parse
    )

    result = collect_feed("테스트", "https://example.com/rss", COLLECTED_AT)

    assert result.is_healthy is True
    assert result.article_count == 1
    assert result.skipped_count == 2


def test_collect_all_feeds_keeps_failures(monkeypatch) -> None:
    """
    한 소스가 실패해도 나머지 소스의 수집 결과는 유지된다.
    """

    def fake_parse(url):
        if "broken" in url:
            return {"entries": [], "bozo_exception": "syntax error"}
        return {"entries": [{"title": "기사", "link": "https://example.com/1"}]}

    monkeypatch.setattr(
        "news_weaver.collectors.rss_collector.feedparser.parse", fake_parse
    )

    sources = (
        RssSource("정상소스", "https://example.com/ok"),
        RssSource("장애소스", "https://example.com/broken"),
    )

    results = collect_all_feeds(sources, COLLECTED_AT)

    assert len(results) == 2
    assert results[0].is_healthy is True
    assert results[0].article_count == 1
    assert results[1].is_healthy is False