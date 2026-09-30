# NewsWeaver/src/news_weaver/db/delivery_repository.py

"""
발송 이력의 조회와 저장을 담당한다.

무엇을 보낼지의 판단은 deliver/history.py의 순수 함수가 맡고, 이 모듈은
그 판단에 필요한 사실(오늘 보냈는지, 어떤 기사를 보냈는지)만 읽고 쓴다.
"""

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from news_weaver.db.tables import DeliveryRow
from news_weaver.deliver.history import DeliveryContents


class DeliveryRepository:
    """deliveries 테이블에 대한 읽기와 쓰기를 담당한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def has_delivered_on(self, delivery_date: date, recipient: str) -> bool:
        """해당 날짜에 이 수신자에게 이미 보냈는지 확인한다."""
        statement = (
            select(DeliveryRow.id)
            .where(
                DeliveryRow.delivery_date == delivery_date,
                DeliveryRow.recipient == recipient,
            )
            .limit(1)
        )

        return self._session.execute(statement).first() is not None

    def find_delivered_url_hashes(self, url_hashes: list[str]) -> set[str]:
        """
        주어진 기사 중 이전에 보낸 적이 있는 것을 찾는다.

        기간으로 자르지 않고 후보 자체로 조회한다. 후보 창을 늘려도 이미
        보낸 기사가 다시 나가지 않게 하기 위함이다.
        """
        if not url_hashes:
            return set()

        # 배열이 겹치는 발송만 고른 뒤 펼친다. 펼친 값에는 후보 밖의 기사도
        # 섞이므로 마지막에 후보와 교집합을 취한다
        statement = (
            select(func.unnest(DeliveryRow.url_hashes))
            .where(DeliveryRow.url_hashes.overlap(url_hashes))
            .distinct()
        )

        rows = self._session.execute(statement).scalars().all()

        return set(rows) & set(url_hashes)

    def record_delivery(
        self,
        delivery_date: date,
        recipient: str,
        subject: str,
        contents: DeliveryContents,
        sent_at: datetime,
    ) -> None:
        """발송 한 건을 기록한다. 발송에 성공한 뒤에만 호출해야 한다."""
        self._session.add(
            DeliveryRow(
                delivery_date=delivery_date,
                recipient=recipient,
                subject=subject,
                content_keys=list(contents.content_keys),
                url_hashes=list(contents.url_hashes),
                sent_at=sent_at,
            )
        )
