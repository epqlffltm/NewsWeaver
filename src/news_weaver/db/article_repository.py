# NewsWeaver/src/news_weaver/db/article_repository.py

"""
기사 저장과 조회를 담당한다.

SQL과 테이블 구조에 대한 지식을 이 모듈 안에 가둬, 파이프라인 상위 단계가
저장 방식을 몰라도 되게 한다. 벡터 검색처럼 ORM으로 표현하기 어려운 쿼리를
raw SQL로 작성하더라도 그 범위는 이 클래스 내부에 머문다.
"""

from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from news_weaver.db.tables import ArticleRow
from news_weaver.domain.article import Article
from news_weaver.embedding.base import EmbeddingResult


class ArticleRepository:
    """articles 테이블에 대한 읽기와 쓰기를 담당한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_articles(self, articles: list[Article]) -> int:
        """기사 목록을 저장한다. 중복은 무시하고 새로 저장된 건수를 반환한다."""
        if not articles:
            return 0

        rows = [_to_row_values(article) for article in articles]

        statement = (
            insert(ArticleRow)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["url_hash"])
            .returning(ArticleRow.id)
        )

        inserted_ids = self._session.execute(statement).scalars().all()

        return len(inserted_ids)

    def find_articles_without_embedding(
        self,
        model_name: str,
        limit: int,
    ) -> list[Article]:
        """
        임베딩이 없거나 다른 모델로 만들어진 기사를 찾는다.

        모델을 바꾸면 기존 벡터는 다른 공간에 있어 비교할 수 없으므로
        재생성 대상이 된다. 조건에 모델명을 포함해 별도의 무효화 처리 없이
        점진적으로 교체되게 한다.
        """
        statement = (
            select(ArticleRow)
            .where(
                or_(
                    ArticleRow.embedding.is_(None),
                    ArticleRow.embedding_model != model_name,
                )
            )
            .order_by(ArticleRow.collected_at.desc())
            .limit(limit)
        )

        rows = self._session.execute(statement).scalars().all()

        return [_to_article(row) for row in rows]

    def save_embeddings(self, results: list[EmbeddingResult]) -> int:
        """
        성공한 임베딩을 기사에 반영하고 갱신 건수를 반환한다.

        실패한 결과를 저장하면 다음 실행에서 재시도할 수 없으므로 제외한다.
        """
        embedded_at = datetime.now(UTC)
        updated_count = 0

        for result in results:
            if not result.is_success:
                continue

            statement = (
                update(ArticleRow)
                .where(ArticleRow.url_hash == result.url_hash)
                .values(
                    embedding=result.vector,
                    embedding_model=result.model_name,
                    embedded_at=embedded_at,
                )
            )
            updated_count += self._session.execute(statement).rowcount

        return updated_count

    def find_similarity_pairs(
        self,
        url_hashes: list[str],
        model_name: str,
        minimum_similarity: float,
    ) -> list[tuple[str, str, float]]:
        """
        주어진 기사들 사이에서 임계값 이상 유사한 쌍을 찾는다.

        준중복 판정에는 개별 기사의 이웃이 아니라 후보 집합 내부의 관계가
        필요하다. 쌍마다 조회하면 왕복이 제곱으로 늘어나므로 한 번에 가져온다.

        a.url_hash < b.url_hash 조건으로 같은 쌍이 두 번 나오는 것을 막는다.
        """
        if len(url_hashes) < 2:
            return []

        statement = text("""
            SELECT
                a.url_hash AS left_hash,
                b.url_hash AS right_hash,
                1 - (a.embedding <=> b.embedding) AS similarity
            FROM articles AS a
            JOIN articles AS b
              ON a.url_hash < b.url_hash
            WHERE a.url_hash = ANY(:hashes)
              AND b.url_hash = ANY(:hashes)
              AND a.embedding IS NOT NULL
              AND b.embedding IS NOT NULL
              AND a.embedding_model = :model_name
              AND b.embedding_model = :model_name
              AND 1 - (a.embedding <=> b.embedding) >= :minimum
            ORDER BY similarity DESC
        """)

        rows = self._session.execute(
            statement,
            {
                "hashes": url_hashes,
                "model_name": model_name,
                "minimum": minimum_similarity,
            },
        ).all()

        return [(row.left_hash, row.right_hash, row.similarity) for row in rows]


def _to_row_values(article: Article) -> dict:
    """도메인 모델을 테이블에 맞는 딕셔너리로 변환한다."""
    values = asdict(article)

    # content 컬럼은 아직 존재하지 않는다. 본문 저장이 필요해지는 시점에
    # 마이그레이션으로 추가한다.
    values.pop("content", None)

    return values


def _to_article(row: ArticleRow) -> Article:
    """ORM 행을 도메인 모델로 변환한다."""
    return Article(
        source_name=row.source_name,
        title=row.title,
        url=row.url,
        url_hash=row.url_hash,
        collected_at=row.collected_at,
        published_at=row.published_at,
        author=row.author,
        summary=row.summary,
    )


def _row_to_article(row) -> Article:
    """raw SQL 결과 행을 도메인 모델로 변환한다."""
    return Article(
        source_name=row.source_name,
        title=row.title,
        url=row.url,
        url_hash=row.url_hash,
        collected_at=row.collected_at,
        published_at=row.published_at,
        author=row.author,
        summary=row.summary,
    )