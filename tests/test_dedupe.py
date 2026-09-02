# NewsWeaver/tests/test_dedupe.py

"""
유사 기사 그룹화가 같은 사건을 하나로 묶고 대표를 올바르게 고르는지 검증한다.
"""

from datetime import UTC, datetime

from news_weaver.domain.article import Article
from news_weaver.selection.dedupe import group_similar_articles, take_representatives
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


def test_single_article_becomes_its_own_group() -> None:
    """
    짝이 없는 기사도 구성원이 하나인 그룹이 된다.

    호출자가 단일 기사와 묶인 기사를 나눠 처리하지 않아도 되게 한다.
    """
    scored = [make_scored("a", "첫째", 9), make_scored("b", "둘째", 6)]

    groups = group_similar_articles(scored, [])

    assert len(groups) == 2
    assert all(group.size == 1 for group in groups)


def test_similar_pair_forms_one_group() -> None:
    """유사한 두 기사가 하나의 그룹으로 묶인다."""
    scored = [make_scored("a", "대표", 9), make_scored("b", "중복", 6)]

    groups = group_similar_articles(scored, [("a", "b", 0.7)])

    assert len(groups) == 1
    assert groups[0].size == 2


def test_highest_score_becomes_representative() -> None:
    """
    점수가 가장 높은 기사가 그룹을 대표한다.

    선별 점수가 이미 관심도 순위이므로 대표 선정의 기준으로 삼는다.
    """
    scored = [make_scored("a", "대표", 9), make_scored("b", "중복", 6)]

    groups = group_similar_articles(scored, [("a", "b", 0.7)])

    assert groups[0].representative.article.url_hash == "a"
    assert [item.article.url_hash for item in groups[0].others] == ["b"]


def test_three_similar_articles_form_one_group() -> None:
    """
    A와 B, B와 C가 유사하면 셋이 한 그룹이 된다.

    A와 C가 직접 비교되지 않아도 같은 사건으로 묶여야 한다.
    """
    scored = [
        make_scored("a", "대표", 9),
        make_scored("b", "중복1", 6),
        make_scored("c", "중복2", 3),
    ]
    pairs = [("a", "b", 0.7), ("b", "c", 0.68)]

    groups = group_similar_articles(scored, pairs)

    assert len(groups) == 1
    assert groups[0].size == 3


def test_unrelated_articles_stay_separate() -> None:
    """서로 다른 사건은 각각의 그룹으로 남는다."""
    scored = [
        make_scored("a", "AI 기사", 9),
        make_scored("b", "AI 중복", 6),
        make_scored("c", "반도체 기사", 6),
    ]

    groups = group_similar_articles(scored, [("a", "b", 0.7)])

    assert len(groups) == 2
    assert groups[0].size == 2
    assert groups[1].size == 1


def test_group_order_follows_input() -> None:
    """그룹 순서는 대표 기사의 입력 순서를 따른다."""
    scored = [
        make_scored("a", "첫째", 9),
        make_scored("b", "둘째", 6),
        make_scored("c", "셋째", 3),
    ]

    groups = group_similar_articles(scored, [("a", "c", 0.7)])

    assert [g.representative.article.url_hash for g in groups] == ["a", "b"]


def test_group_key_ignores_member_order() -> None:
    """
    구성원이 같으면 순서와 무관하게 같은 키가 된다.

    캐시 키로 쓰이므로 같은 구성에 대해 항상 같은 값이어야 한다.
    """
    forward = group_similar_articles(
        [make_scored("a", "A", 9), make_scored("b", "B", 6)],
        [("a", "b", 0.7)],
    )
    backward = group_similar_articles(
        [make_scored("b", "B", 9), make_scored("a", "A", 6)],
        [("a", "b", 0.7)],
    )

    assert forward[0].group_key == backward[0].group_key


def test_group_key_changes_when_member_added() -> None:
    """
    구성원이 추가되면 키가 달라진다.

    구성이 바뀌면 종합 결과도 달라지므로 캐시를 재사용하면 안 된다.
    """
    two = group_similar_articles(
        [make_scored("a", "A", 9), make_scored("b", "B", 6)],
        [("a", "b", 0.7)],
    )
    three = group_similar_articles(
        [make_scored("a", "A", 9), make_scored("b", "B", 6), make_scored("c", "C", 3)],
        [("a", "b", 0.7), ("b", "c", 0.7)],
    )

    assert two[0].group_key != three[0].group_key


def test_take_representatives_returns_one_per_group() -> None:
    """그룹마다 대표 하나씩만 뽑는다."""
    scored = [
        make_scored("a", "대표", 9),
        make_scored("b", "중복", 6),
        make_scored("c", "별개", 6),
    ]

    groups = group_similar_articles(scored, [("a", "b", 0.7)])
    representatives = take_representatives(groups)

    assert [item.article.url_hash for item in representatives] == ["a", "c"]


def test_empty_input() -> None:
    """선별된 기사가 없어도 실패하지 않는다."""
    assert group_similar_articles([], []) == []