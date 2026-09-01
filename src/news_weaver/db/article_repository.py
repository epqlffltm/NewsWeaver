# NewsWeaver/src/news_weaver/db/article_repository.py

"""
기사 저장과 조회를 담당한다.

SQL과 테이블 구조에 대한 지식을 이 모듈 안에 가둬, 파이프라인 상위 단계가
저장 방식을 몰라도 되게 한다. 나중에 벡터 검색처럼 ORM으로 표현하기 어려운
쿼리를 raw SQL로 작성하더라도 그 범위는 이 클래스 내부에 머문다.
"""

from dataclasses import asdict

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from news_weaver.db.tables import ArticleRow
from news_weaver.domain.article import Article


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


def _to_row_values(article: Article) -> dict:
    """도메인 모델을 테이블에 맞는 딕셔너리로 변환한다."""
    values = asdict(article)

    # content 컬럼은 아직 존재하지 않는다. 본문 저장이 필요해지는 시점에
    # 마이그레이션으로 추가한다.
    values.pop("content", None)

    return values