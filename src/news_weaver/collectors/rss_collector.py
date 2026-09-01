# NewsWeaver/src/news_weaver/collectors/rss_collector.py

"""
RSS 피드를 수집해 Article 목록으로 변환한다.

피드마다 제공하는 필드와 시각 표기가 제각각이므로, 그 차이를 흡수해
파이프라인 뒷단이 다루는 단일한 표현으로 정규화하는 것이 이 모듈의 책임이다.
"""

import re
from datetime import UTC, datetime, timedelta, timezone

import feedparser

from news_weaver.collectors.result import CollectionResult
from news_weaver.domain.article import Article
from news_weaver.pipeline.clean_text import clean_summary
from news_weaver.pipeline.normalize import hash_url, normalize_url

# RFC 822 계열 날짜 문자열의 끝에 오는 타임존 표기를 찾는다.
# 예: "+0900", "-0500", "GMT", "Z"
TIMEZONE_MARKER_PATTERN = re.compile(r"(?:[+-]\d{2}:?\d{2}|Z|[A-Z]{2,4})\s*$")

# 타임존 표기가 없는 피드는 한국 언론사 기준으로 KST로 간주한다
KST = timezone(timedelta(hours=9))


def _has_timezone_marker(published_raw: str) -> bool:
    """
    발행 시각 문자열에 타임존 표기가 있는지 판정한다.

    feedparser는 표기가 있을 때만 published_parsed를 UTC로 변환하므로,
    이 판정 결과에 따라 후속 처리가 달라진다.
    """
    return TIMEZONE_MARKER_PATTERN.search(published_raw) is not None


def to_utc_datetime(published_raw: str | None, published_parsed) -> datetime | None:
    """
    피드의 발행 시각을 타임존을 가진 UTC datetime으로 변환한다.

    한국 언론사 피드를 전제로, 타임존 표기가 없는 경우 KST로 간주한다.
    해외 소스를 추가할 때는 이 가정을 재검토해야 한다.
    """
    if published_parsed is None:
        return None

    naive = datetime(*published_parsed[:6])# noqa: DTZ001

    if _has_timezone_marker(published_raw or ""):
        # feedparser가 이미 UTC로 변환했다
        return naive.replace(tzinfo=UTC)

    # 원본 시각이 그대로 남아 있으므로 KST로 간주해 변환한다
    return naive.replace(tzinfo=KST).astimezone(UTC)

def _extract_author(entry) -> str | None:
    """
    작성자를 꺼낸다. 제공하지 않는 소스가 있어 없으면 None을 반환한다.
    """
    
    author = entry.get("author")
    if not author:
        return None
    return author.strip()

def to_article(entry, source_name: str, collected_at: datetime) -> Article | None:
    """
    RSS 항목 하나를 Article로 변환한다.

    제목이나 링크가 없는 항목은 식별과 요약이 불가능하므로 None을 반환한다.
    한 건의 실패가 나머지 수집을 중단시키지 않도록, 예외 대신 None으로 알린다.
    """
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()

    if not title or not link:
        return None

    normalized_url = normalize_url(link)

    return Article(
        source_name=source_name,
        title=title,
        url=link,
        url_hash=hash_url(normalized_url),
        collected_at=collected_at,
        published_at=to_utc_datetime(
            entry.get("published"),
            entry.get("published_parsed"),
        ),
        author=_extract_author(entry),
        summary=clean_summary(entry.get("summary")),
    )
    
def collect_feed(
    source_name: str,
    feed_url: str,
    collected_at: datetime,
) -> CollectionResult:
    """
    RSS 피드 하나를 수집해 Article 목록과 건강 상태를 함께 반환한다.

    feedparser는 파싱에 실패해도 예외 대신 빈 결과를 돌려주므로,
    항목 수가 0인 경우를 정상 상태와 구분해 기록한다.
    """
    parsed_feed = feedparser.parse(feed_url)
    entries = parsed_feed.get("entries") or []

    if not entries:
        return CollectionResult(
            source_name=source_name,
            is_healthy=False,
            error=str(parsed_feed.get("bozo_exception") or "항목이 없음"),
        )

    articles: list[Article] = []
    skipped_count = 0

    for entry in entries:
        article = to_article(entry, source_name, collected_at)
        if article is None:
            skipped_count += 1
            continue
        articles.append(article)

    return CollectionResult(
        source_name=source_name,
        articles=articles,
        skipped_count=skipped_count,
    )