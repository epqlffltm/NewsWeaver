# NewsWeaver/tests/test_render.py

"""
다이제스트 본문이 원문 링크와 특수문자를 올바르게 다루는지 검증한다.
"""

from datetime import UTC, datetime

from news_weaver.deliver.render import build_subject, render_digest
from news_weaver.domain.article import Article
from news_weaver.summarize.service import SummarizedArticle

COLLECTED_AT = datetime(2026, 9, 2, 6, 0, tzinfo=UTC)
PUBLISHED_AT = datetime(2026, 9, 1, 4, 13, tzinfo=UTC)
SENT_AT = datetime(2026, 9, 2, 7, 0, tzinfo=UTC)


def make_item(
    title: str = "제목",
    summary_text: str = "요약문",
    url: str = "https://zdnet.co.kr/view/?no=123&utm_source=naver",
    published_at: datetime | None = PUBLISHED_AT,
) -> SummarizedArticle:
    """테스트용 요약 결과를 만든다."""
    article = Article(
        source_name="ZDNet",
        title=title,
        url=url,
        url_hash="hash",
        collected_at=COLLECTED_AT,
        published_at=published_at,
    )
    return SummarizedArticle(article, summary_text)


def test_subject_contains_date_and_count() -> None:
    """제목에 날짜와 기사 수가 들어간다."""
    subject = build_subject(SENT_AT, 5)

    assert "2026-09-02" in subject
    assert "5" in subject


def test_body_uses_original_url() -> None:
    """
    링크에는 정규화하지 않은 원본 주소를 쓴다.

    정규화된 주소는 중복 판정용이며 실제 접속에는 쓰지 않는다.
    """
    body = render_digest([make_item()], SENT_AT)

    assert "utm_source=naver" in body


def test_body_escapes_special_characters() -> None:
    """
    제목에 든 특수문자가 마크업으로 해석되지 않는다.

    기사 제목은 외부에서 온 텍스트이므로 그대로 넣으면 본문이 깨진다.
    """
    body = render_digest([make_item(title="AT&T <합병> 발표")], SENT_AT)

    assert "&amp;" in body
    assert "<합병>" not in body


def test_body_falls_back_to_collected_at() -> None:
    """발행 시각이 없는 소스는 수집 시각을 대신 표시한다."""
    body = render_digest([make_item(published_at=None)], SENT_AT)

    assert "2026-09-02 06:00" in body


def test_body_contains_all_articles() -> None:
    """전달된 기사가 모두 본문에 들어간다."""
    items = [make_item(title="첫째"), make_item(title="둘째")]

    body = render_digest(items, SENT_AT)

    assert "첫째" in body
    assert "둘째" in body


def test_empty_digest_still_renders() -> None:
    """요약된 기사가 없어도 본문 생성이 실패하지 않는다."""
    body = render_digest([], SENT_AT)

    assert "다이제스트" in body