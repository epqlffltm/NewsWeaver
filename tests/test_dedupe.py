# NewsWeaver/tests/test_dedupe.py

"""
준중복 제거가 같은 사건의 기사를 묶고 점수 높은 것을 남기는지 검증한다.
"""

from datetime import UTC, datetime

from news_weaver.domain.article import Article
from news_weaver.selection.dedupe import remove_near_duplicates
from news_weaver.selection.keyword import ScoredArticle

COLLECTED_AT = datetime(2026, 9, 2, 6, 0, tzinfo=UTC)


def make_scored(url_hash: str, title: str, score: int) -> ScoredArticle:
    """테스트용 선별 결과를 만든다."""
    article = Article(
        source_name="테스트",
        title=title,
        url=f"https://example.com/{url_hash}",
        url_hash=url_hash,
        collected_at=COLLECTED_AT,
    )
    return ScoredArticle(article=article, score=score, matched_topics=("AI",))


def test_keeps_all_when_no_pairs() -> None:
    """유사한 쌍이 없으면 모두 남는다."""
    scored = [make_scored("a", "첫째", 9), make_scored("b", "둘째", 6)]

    report = remove_near_duplicates(scored, [])

    assert len(report.kept) == 2
    assert report.removed == []


def test_removes_lower_scored_duplicate() -> None:
    """
    유사한 쌍에서 점수가 낮은 쪽이 제외된다.

    선별 점수가 이미 관심도 순위이므로 대표 선정의 기준으로 삼는다.
    """
    scored = [make_scored("a", "대표", 9), make_scored("b", "중복", 6)]

    report = remove_near_duplicates(scored, [("a", "b", 0.7)])

    assert [item.article.url_hash for item in report.kept] == ["a"]
    assert report.removed == [("중복", "대표")]


def test_groups_three_similar_articles() -> None:
    """같은 사건을 다룬 셋이 묶여 하나만 남는다."""
    scored = [
        make_scored("a", "대표", 9),
        make_scored("b", "중복1", 6),
        make_scored("c", "중복2", 3),
    ]
    pairs = [("a", "b", 0.7), ("a", "c", 0.65), ("b", "c", 0.68)]

    report = remove_near_duplicates(scored, pairs)

    assert len(report.kept) == 1
    assert len(report.removed) == 2


def test_unrelated_pair_survives() -> None:
    """서로 다른 사건이면 유사 쌍이 있어도 각각 남는다."""
    scored = [
        make_scored("a", "AI 기사", 9),
        make_scored("b", "AI 중복", 6),
        make_scored("c", "반도체 기사", 6),
    ]

    report = remove_near_duplicates(scored, [("a", "b", 0.7)])

    assert [item.article.url_hash for item in report.kept] == ["a", "c"]


def test_keeps_order() -> None:
    """남은 기사의 순서는 입력 순서를 따른다."""
    scored = [
        make_scored("a", "첫째", 9),
        make_scored("b", "둘째", 6),
        make_scored("c", "셋째", 3),
    ]

    report = remove_near_duplicates(scored, [("a", "c", 0.7)])

    assert [item.article.url_hash for item in report.kept] == ["a", "b"]


def test_empty_input() -> None:
    """선별된 기사가 없어도 실패하지 않는다."""
    report = remove_near_duplicates([], [])

    assert report.kept == []