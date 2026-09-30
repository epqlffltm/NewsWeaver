# NewsWeaver/tests/test_repositories_integration.py

"""
Repository의 SQL이 실제 PostgreSQL(pgvector)에서 의도대로 동작하는지 검증한다.

ON CONFLICT, 벡터 거리 연산, 배열 겹침처럼 DB에 의존하는 동작은 가짜로
대체하면 검증이 되지 않으므로 실제 DB로 확인한다.
"""

from datetime import UTC, date, datetime

import pytest

from news_weaver.db.article_repository import ArticleRepository
from news_weaver.db.delivery_repository import DeliveryRepository
from news_weaver.deliver.history import DeliveryContents
from news_weaver.domain.article import Article
from news_weaver.embedding.fake import FAKE_MODEL_NAME, FakeEmbedder

pytestmark = pytest.mark.integration

COLLECTED_AT = datetime(2026, 9, 2, 6, 0, tzinfo=UTC)

# 실제 해시와 겹치지 않도록 접두사를 붙인다
PREFIX = "it-"


def make_article(key: str, title: str, summary: str | None = None) -> Article:
    """테스트용 기사를 만든다."""
    return Article(
        source_name="테스트",
        title=title,
        url=f"https://example.com/{key}",
        url_hash=f"{PREFIX}{key}",
        collected_at=COLLECTED_AT,
        summary=summary,
    )


def test_save_articles_ignores_duplicates(db_session) -> None:
    """
    같은 기사를 다시 저장하면 무시되고 새 건수만 센다.

    배치를 재실행해도 기사가 두 번 쌓이지 않아야 한다.
    """
    repository = ArticleRepository(db_session)
    articles = [make_article("a", "첫째"), make_article("b", "둘째")]

    assert repository.save_articles(articles) == 2
    assert repository.save_articles(articles) == 0
    assert repository.save_articles([make_article("c", "셋째")]) == 1


def test_similarity_pairs_return_only_close_pairs(db_session) -> None:
    """
    임계값 이상인 쌍만, 같은 쌍은 한 번만 돌려준다.

    가짜 임베딩은 같은 텍스트에 같은 벡터를 주므로, 제목과 요약이 같은
    두 기사만 유사도 1로 묶인다.
    """
    repository = ArticleRepository(db_session)
    articles = [
        make_article("a", "같은 사건", "같은 요약"),
        make_article("b", "같은 사건", "같은 요약"),
        make_article("c", "다른 사건", "다른 요약"),
    ]
    repository.save_articles(articles)
    assert repository.save_embeddings(FakeEmbedder().embed(articles)) == 3

    pairs = repository.find_similarity_pairs(
        [article.url_hash for article in articles],
        FAKE_MODEL_NAME,
        0.999,
    )

    assert [(left, right) for left, right, _ in pairs] == [
        (f"{PREFIX}a", f"{PREFIX}b")
    ]
    assert pairs[0][2] == pytest.approx(1.0)


def test_similarity_pairs_ignore_other_models(db_session) -> None:
    """다른 모델로 만든 벡터는 비교하지 않는다. 벡터 공간이 다르기 때문이다."""
    repository = ArticleRepository(db_session)
    articles = [make_article("a", "같은 사건"), make_article("b", "같은 사건")]
    repository.save_articles(articles)
    repository.save_embeddings(FakeEmbedder().embed(articles))

    pairs = repository.find_similarity_pairs(
        [article.url_hash for article in articles],
        "other-model",
        0.5,
    )

    assert pairs == []


def test_delivery_history_round_trip(db_session) -> None:
    """
    기록한 발송이 날짜·수신자 조회와 기사 제외 조회에 반영된다.

    후보 밖의 기사는 결과에 섞이지 않아야 한다.
    """
    repository = DeliveryRepository(db_session)
    delivery_date = date(2000, 1, 1)
    recipient = "integration@example.com"

    assert repository.has_delivered_on(delivery_date, recipient) is False

    repository.record_delivery(
        delivery_date,
        recipient,
        "제목",
        DeliveryContents(
            content_keys=("group-key",),
            url_hashes=(f"{PREFIX}a", f"{PREFIX}b"),
        ),
        datetime(2000, 1, 1, 0, 0, tzinfo=UTC),
    )
    db_session.flush()

    assert repository.has_delivered_on(delivery_date, recipient) is True
    assert repository.has_delivered_on(date(2000, 1, 2), recipient) is False
    assert repository.find_delivered_url_hashes(
        [f"{PREFIX}a", f"{PREFIX}c"]
    ) == {f"{PREFIX}a"}
    assert repository.find_delivered_url_hashes([]) == set()


def test_find_articles_by_hashes_ignores_collection_time(db_session) -> None:
    """
    수집 시각과 무관하게 지정한 기사만 읽어온다.

    평가 대상이 실행 날짜에 따라 바뀌지 않게 하기 위함이다.
    """
    repository = ArticleRepository(db_session)
    repository.save_articles(
        [make_article("old", "오래된 기사"), make_article("other", "다른 기사")]
    )

    found = repository.find_articles_by_hashes([f"{PREFIX}old", f"{PREFIX}none"])

    assert [article.url_hash for article in found] == [f"{PREFIX}old"]
