# NewsWeaver/src/news_weaver/db/tables.py

"""
데이터베이스 테이블 정의.

도메인 모델(Article)과 분리해 둔다. 도메인 모델은 저장 방식을 몰라야 하고,
반대로 테이블은 인덱스나 제약처럼 저장에만 필요한 관심사를 갖기 때문이다.
두 표현 사이의 변환은 Repository가 담당한다.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """모든 테이블 정의가 상속하는 기반 클래스."""


class ArticleRow(Base):
    """수집된 기사를 저장하는 테이블."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)

    source_name: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)

    # 중복 저장을 막는 최종 방어선. 애플리케이션 확인만으로는
    # 동시 실행 시 중복이 통과할 수 있다
    url_hash: Mapped[str] = mapped_column(String(64), unique=True)

    # 발행 시각이 없는 소스가 있어 정렬의 기준으로 항상 사용 가능해야 한다
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # "최근 기사 N건" 조회가 주 사용 패턴이므로 발행 시각 역순 인덱스를 둔다
        Index("ix_articles_published_at", published_at.desc()),
        Index("ix_articles_source_name", source_name),
    )