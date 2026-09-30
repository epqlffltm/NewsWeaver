# NewsWeaver/src/news_weaver/db/tables.py

"""
데이터베이스 테이블 정의.

도메인 모델(Article)과 분리해 둔다. 도메인 모델은 저장 방식을 몰라야 하고,
반대로 테이블은 인덱스나 제약처럼 저장에만 필요한 관심사를 갖기 때문이다.
두 표현 사이의 변환은 Repository가 담당한다.
"""

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 벡터 컬럼 타입에 고정되는 값. 변경하려면 마이그레이션과 전체 재임베딩이 필요하다.
# .env의 EMBEDDING_DIMENSION과 반드시 일치해야 한다
EMBEDDING_DIMENSION = 768


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
    
        # 임베딩은 선별과 준중복 판정에 쓰인다. 아직 생성되지 않은 기사도 있으므로
    # nullable이며, 모델이 바뀌면 점진적으로 다시 만든다
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )

    # 어떤 모델로 만든 벡터인지. 벡터 공간이 다르면 유사도 비교가 무의미하므로
    # 모델 교체 시 대상을 골라내는 근거가 된다
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    embedded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # 선별 후보 조회(find_recent_articles)와 임베딩 대상 조회가 모두 수집
        # 시각으로 거르고 정렬하므로 수집 시각 역순 인덱스를 둔다. 발행 시각은
        # 소스마다 비어 있을 수 있어 조회 조건으로 쓰지 않으므로 인덱스가 없다
        Index("ix_articles_collected_at", collected_at.desc()),
        Index("ix_articles_source_name", source_name),
    )
    
class SummaryRow(Base):
    """
    기사 브리핑 캐시.

    요약은 건당 수십 초에서 수 분이 걸리므로 배치를 재실행할 때마다 다시
    만들면 안 된다. 다만 모델이나 프롬프트가 바뀌면 결과가 달라지므로,
    그 조건을 키에 포함해 조건이 바뀌면 자동으로 다시 생성되게 한다.
    """

    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(primary_key=True)

    # 요약 대상을 식별하는 키. 단일 기사가 아니라 같은 사건으로 묶인
    # 기사 그룹일 수 있으므로 url_hash가 아니라 별도 키를 쓴다
    content_key: Mapped[str] = mapped_column(String(64))

    summary_text: Mapped[str] = mapped_column(Text)

    # 어떤 조건에서 만든 요약인지. 캐시 적중 판정의 키이자 품질 추적의 근거
    model_name: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        # 같은 대상이라도 모델이나 프롬프트가 다르면 별개의 요약으로 본다
        UniqueConstraint(
            "content_key",
            "model_name",
            "prompt_version",
            name="uq_summaries_content_and_config",
        ),
        Index("ix_summaries_content_key", "content_key"),
    )


class DeliveryRow(Base):
    """
    다이제스트 발송 이력.

    선별 후보가 최근 며칠치라, 기록이 없으면 이미 보낸 기사가 다음 날 다시
    실리고 같은 날 재실행하면 두 번 발송된다. 발송에 성공한 경우에만 남긴다.
    """

    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)

    # "오늘 이미 보냈는가"의 기준. 한국 시간 날짜로 저장한다
    delivery_date: Mapped[date] = mapped_column(Date)

    recipient: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(Text)

    # 실린 브리핑의 그룹 키와 구성 기사. 발송 단위로 한 번에 쓰고 읽으므로
    # 별도 테이블 대신 배열로 둔다
    content_keys: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
    url_hashes: Mapped[list[str]] = mapped_column(ARRAY(String(64)))

    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # 강제 재발송을 허용하므로 유일 제약 대신 조회용 인덱스만 둔다
        Index("ix_deliveries_date_recipient", "delivery_date", "recipient"),
    )
