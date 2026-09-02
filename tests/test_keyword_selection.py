# NewsWeaver/tests/test_keyword_selection.py

"""
키워드 선별이 관심 기사를 우선순위대로 골라내는지 검증한다.
"""

from datetime import UTC, datetime

from news_weaver.domain.article import Article
from news_weaver.selection.keyword import (
    TITLE_MATCH_SCORE,
    score_article,
    select_articles,
)

COLLECTED_AT = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)


def make_article(title: str, summary: str | None = None) -> Article:
    """테스트용 기사를 만든다. 선별에 쓰이지 않는 필드는 최소값으로 채운다."""
    return Article(
        source_name="테스트",
        title=title,
        url=f"https://example.com/{abs(hash(title))}",
        url_hash=str(abs(hash(title))),
        collected_at=COLLECTED_AT,
        summary=summary,
    )


def test_title_match_scores_higher_than_summary() -> None:
    """제목에 걸린 기사가 요약에만 걸린 기사보다 높은 점수를 받는다."""
    in_title = score_article(make_article("AI 반도체 신제품"), ("AI",))
    in_summary = score_article(make_article("신제품 공개", "AI 기능 탑재"), ("AI",))

    assert in_title.score > in_summary.score


def test_multiple_keywords_accumulate() -> None:
    """여러 키워드에 걸리면 점수가 합산되고 걸린 키워드가 모두 기록된다."""
    result = score_article(
        make_article("AI 반도체 시장 전망"),
        ("AI", "반도체"),
    )

    assert result.matched_keywords == ("AI", "반도체")
    assert result.score == TITLE_MATCH_SCORE * 2


def test_matching_ignores_case() -> None:
    """대소문자가 달라도 같은 키워드로 본다."""
    result = score_article(make_article("ai 기술 동향"), ("AI",))

    assert result.score > 0


def test_unmatched_article_is_excluded() -> None:
    """어떤 키워드에도 걸리지 않은 기사는 선별되지 않는다."""
    articles = [make_article("날씨가 맑습니다")]

    assert select_articles(articles, ("AI",), limit=10) == []


def test_selection_respects_limit() -> None:
    """상한을 넘는 기사는 점수가 높은 순으로 잘린다."""
    articles = [
        make_article("AI 동향"),
        make_article("AI 반도체 클라우드"),
        make_article("AI 반도체"),
    ]

    selected = select_articles(articles, ("AI", "반도체", "클라우드"), limit=2)

    assert len(selected) == 2
    assert selected[0].score > selected[1].score


def test_summary_none_does_not_crash() -> None:
    """요약을 제공하지 않는 소스의 기사도 처리된다."""
    result = score_article(make_article("AI 관련 기사", None), ("AI",))

    assert result.score == TITLE_MATCH_SCORE